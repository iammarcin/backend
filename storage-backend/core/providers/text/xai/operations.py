"""Operational helpers for xAI Grok text generation."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, AsyncIterator, Optional, Set

if TYPE_CHECKING:
    from features.chat.utils.websocket_runtime import WorkflowRuntime

from core.pydantic_schemas import ProviderResponse
from core.streaming.manager import StreamingManager

from .tool_events import emit_xai_tool_events
from ..xai_messages import prepare_messages
from ..xai_parameters import (
    build_tool_payload,
    ensure_default_server_side_tools,
    filter_request_kwargs,
    resolve_model_alias,
)
from ..xai_responses import (
    format_usage,
    handle_grpc_exception,
    log_server_side_tool_usage,
    normalise_tool_calls,
    tool_calls_require_client_action,
)

if TYPE_CHECKING:  # pragma: no cover
    from .provider import XaiTextProvider

logger = logging.getLogger(__name__)


async def generate_text(
    provider: "XaiTextProvider",
    *,
    prompt: str,
    model: Optional[str],
    temperature: float,
    max_tokens: int,
    system_prompt: Optional[str],
    messages: Optional[list[dict[str, Any]]],
    request_kwargs: dict[str, Any],
) -> ProviderResponse:
    formatted, params, _ = await _prepare_request(
        provider=provider,
        prompt=prompt,
        system_prompt=system_prompt,
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        request_kwargs=request_kwargs,
    )

    logger.debug(
        "Dispatching xAI generate | model=%s messages=%d",
        params["model"],
        len(formatted.messages),
    )

    try:
        chat_request = provider.client.chat.create(**params)
        response = await chat_request.sample()
    except Exception as exc:  # pragma: no cover - handled below
        logger.error("xAI generate failed: %s", exc, exc_info=True)
        raise handle_grpc_exception(exc) from exc

    text = response.content or ""
    reasoning = response.reasoning_content or None
    tool_calls = normalise_tool_calls(response.tool_calls)
    usage = format_usage(response)
    citations = list(response.citations) if getattr(response, "citations", None) else []

    if reasoning:
        provider.capabilities.reasoning = True

    metadata: dict[str, Any] = {
        "finish_reason": response.finish_reason,
        "usage": usage,
        "tool_calls": tool_calls or None,
        "response_id": getattr(response, "id", None),
    }

    server_side_usage = getattr(response, "server_side_tool_usage", None)
    if server_side_usage:
        metadata["server_side_tool_usage"] = dict(server_side_usage)

    if citations:
        metadata["citations"] = citations
        provider.capabilities.citations = True

    if formatted.uploaded_file_ids:
        metadata["uploaded_file_ids"] = list(formatted.uploaded_file_ids)

    if not text and tool_calls:
        logger.debug("xAI returned tool calls without final text response")

    log_server_side_tool_usage(
        tool_calls=response.tool_calls,
        citations=citations,
        context="generate",
    )

    return ProviderResponse(
        text=text if text or not tool_calls else "",
        model=params["model"],
        provider="xai",
        reasoning=reasoning,
        citations=[{"text": entry} for entry in citations] if citations else None,
        metadata=metadata,
        tool_calls=tool_calls or None,
    )


async def stream_text(
    provider: "XaiTextProvider",
    *,
    prompt: str,
    model: Optional[str],
    temperature: float,
    max_tokens: int,
    system_prompt: Optional[str],
    messages: Optional[list[dict[str, Any]]],
    runtime: Optional["WorkflowRuntime"] = None,
    request_kwargs: dict[str, Any],
) -> AsyncIterator[str | dict[str, Any]]:
    formatted, params, manager = await _prepare_request(
        provider=provider,
        prompt=prompt,
        system_prompt=system_prompt,
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        request_kwargs=request_kwargs,
    )

    seen_tool_events: Set[str] = set()

    logger.debug(
        "Dispatching xAI stream | model=%s messages=%d",
        params["model"],
        len(formatted.messages),
    )

    try:
        chat_request = provider.client.chat.create(**params)
    except Exception as exc:  # pragma: no cover - handled below
        logger.error("xAI stream setup failed: %s", exc, exc_info=True)
        raise handle_grpc_exception(exc) from exc

    try:
        async for response, chunk in chat_request.stream():
            # Check cancellation
            if runtime and runtime.is_cancelled():
                logger.info(
                    "xAI stream cancelled by user (model=%s)",
                    params["model"],
                )
                break  # Exit loop, close stream

            if chunk.reasoning_content:
                provider.capabilities.reasoning = True
                yield {"type": "reasoning", "content": chunk.reasoning_content}

            if chunk.tool_calls:
                requires_action = tool_calls_require_client_action(chunk.tool_calls)
                log_server_side_tool_usage(
                    tool_calls=chunk.tool_calls,
                    citations=getattr(chunk, "citations", None),
                    context="stream",
                )
                normalised_calls = normalise_tool_calls(chunk.tool_calls)
                if normalised_calls:
                    if manager is not None:
                        await emit_xai_tool_events(
                            calls=normalised_calls,
                            manager=manager,
                            seen=seen_tool_events,
                        )
                    tool_payload = {
                        "value": normalised_calls,
                        "requires_action": requires_action,
                    }
                    yield {
                        "type": "tool_call",
                        "content": tool_payload,
                        "requires_action": requires_action,
                    }
                if requires_action:
                    break
                continue

            if chunk.content:
                yield chunk.content
    except asyncio.CancelledError:
        # Handle explicit task cancellation
        logger.info("xAI stream task cancelled (model=%s)", params["model"])
        raise  # Re-raise for cleanup
    except Exception as exc:  # pragma: no cover - handled below
        logger.error("xAI stream failed: %s", exc, exc_info=True)
        raise handle_grpc_exception(exc) from exc


async def _prepare_request(
    *,
    provider: "XaiTextProvider",
    prompt: str,
    system_prompt: Optional[str],
    messages: Optional[list[dict[str, Any]]],
    model: Optional[str],
    temperature: float,
    max_tokens: int,
    request_kwargs: dict[str, Any],
) -> tuple[Any, dict[str, Any], StreamingManager | None]:
    formatted = await prepare_messages(
        client=provider.client,
        prompt=prompt,
        system_prompt=system_prompt,
        messages=messages,
    )

    tools, tool_choice, parallel_tool_calls = build_tool_payload(
        request_kwargs.pop("tool_settings", None)
    )

    manager: StreamingManager | None = request_kwargs.pop("manager", None)

    params = {
        "model": resolve_model_alias(provider, model),
        "messages": formatted.messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    filtered_kwargs = filter_request_kwargs(request_kwargs)
    params.update(filtered_kwargs)
    if tools:
        params["tools"] = tools
    if tool_choice is not None:
        params["tool_choice"] = tool_choice
    if parallel_tool_calls is not None:
        params["parallel_tool_calls"] = parallel_tool_calls

    ensure_default_server_side_tools(params)
    return formatted, params, manager


__all__ = ["generate_text", "stream_text"]
