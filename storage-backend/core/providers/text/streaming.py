"""OpenAI text streaming logic.

This module contains the stream method implementation for the OpenAI text
provider, handling both standard chat completion streaming and Responses
API streaming modes.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any, AsyncIterator, Optional, Set, Tuple

if TYPE_CHECKING:
    from features.chat.utils.websocket_runtime import WorkflowRuntime

from core.exceptions import ProviderError, RateLimitError
from core.providers.registry.model_config import ModelConfig
from core.streaming.manager import StreamingManager
from features.chat.services.streaming.events import emit_tool_use_event

from .openai_responses import stream_responses_api

logger = logging.getLogger(__name__)


async def stream_text(
    *,
    client: Any,
    model_config: ModelConfig | None,
    prompt: str,
    model: str,
    temperature: float,
    max_tokens: int,
    system_prompt: Optional[str],
    messages: Optional[list[dict[str, Any]]],
    enable_reasoning: bool,
    reasoning_value: Optional[str],
    is_reasoning_model: bool,
    uses_responses_api: bool,
    manager: StreamingManager | None = None,
    runtime: Optional["WorkflowRuntime"] = None,
    **kwargs: Any,
) -> AsyncIterator[str | dict[str, str]]:
    """Stream response chunks from OpenAI."""

    if (not prompt or not prompt.strip()) and not messages:
        raise ProviderError(
            "OpenAI prompt cannot be empty when no message history is provided",
            provider="openai",
        )

    final_messages = list(messages) if messages is not None else []
    if not final_messages:
        if system_prompt and not is_reasoning_model:
            final_messages.append({"role": "system", "content": system_prompt})
        final_messages.append({"role": "user", "content": prompt})

    resolved_reasoning_value: Optional[str] = reasoning_value or kwargs.get(
        "reasoning_effort"
    )

    if uses_responses_api:
        extra_kwargs = dict(kwargs)
        if enable_reasoning and resolved_reasoning_value:
            extra_kwargs["reasoning_effort"] = resolved_reasoning_value
        async for chunk in stream_responses_api(
            client=client,
            model_config=model_config,
            messages=final_messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            manager=manager,
            enable_reasoning=enable_reasoning,
            **extra_kwargs,
        ):
            yield chunk
        return

    params: dict[str, Any] = {
        "model": model,
        "messages": final_messages,
        "stream": True,
        **kwargs,
    }

    if is_reasoning_model:
        params["max_completion_tokens"] = max_tokens
        params["temperature"] = 1.0
        if enable_reasoning and resolved_reasoning_value:
            params["reasoning_effort"] = resolved_reasoning_value
            logger.debug(
                "OpenAI streaming reasoning effort set to %s", resolved_reasoning_value
            )
    else:
        params["temperature"] = temperature
        params["max_tokens"] = max_tokens

    logger.debug(
        "OpenAI stream: model=%s, messages_count=%d, params=%s",
        model,
        len(params.get("messages", [])),
        {
            "temperature": params.get("temperature"),
            "max_tokens": params.get("max_tokens"),
            "max_completion_tokens": params.get("max_completion_tokens"),
            "reasoning_effort": params.get("reasoning_effort"),
            "stream": True,
        },
    )

    try:
        stream = await client.chat.completions.create(**params)
    except Exception as exc:  # pragma: no cover - handled below
        error_msg = str(exc)
        if "rate limit" in error_msg.lower():
            raise RateLimitError(f"OpenAI rate limit: {error_msg}") from exc

        logger.error("OpenAI stream error: %s", exc)
        raise ProviderError(
            f"OpenAI streaming error: {error_msg}",
            provider="openai",
            original_error=exc,
        ) from exc

    seen_tool_calls: Set[Tuple[str | None, str | None, str | None]] = set()

    try:
        async for chunk in stream:
            # Check cancellation
            if runtime and runtime.is_cancelled():
                logger.info(
                    "OpenAI stream cancelled by user (model=%s)",
                    model,
                )
                break  # Exit loop, close stream

            choice = chunk.choices[0]
            delta = getattr(choice, "delta", None)

            await _emit_completion_tool_events(
                delta=delta,
                manager=manager,
                seen=seen_tool_calls,
            )

            content = getattr(delta, "content", None) if delta else None
            if content:
                yield content

            reasoning = None
            if delta and hasattr(delta, "reasoning_content"):
                reasoning = getattr(delta, "reasoning_content", None)
            if reasoning:
                yield {"type": "reasoning", "content": reasoning}

    except asyncio.CancelledError:
        # Handle explicit task cancellation
        logger.info("OpenAI stream task cancelled (model=%s)", model)
        raise  # Re-raise for cleanup


__all__ = ["stream_text"]


async def _emit_completion_tool_events(
    *,
    delta: Any,
    manager: StreamingManager | None,
    seen: Set[Tuple[str | None, str | None, str | None]],
) -> None:
    """Emit tool usage events detected in chat completion deltas."""

    if manager is None or delta is None:
        return

    tool_calls = getattr(delta, "tool_calls", None)
    if tool_calls is None and isinstance(delta, dict):
        tool_calls = delta.get("tool_calls")

    if not tool_calls:
        return

    for call in tool_calls:
        call_dict = call
        if not isinstance(call_dict, dict):
            try:
                call_dict = call.model_dump()  # type: ignore[attr-defined]
            except AttributeError:
                call_dict = {}

        call_id = call_dict.get("id") or call_dict.get("call_id")

        function_payload = call_dict.get("function") or {}
        if not isinstance(function_payload, dict):
            try:
                function_payload = function_payload.model_dump()  # type: ignore[attr-defined]
            except AttributeError:
                function_payload = {}

        tool_name = (
            function_payload.get("name")
            or call_dict.get("name")
            or call_dict.get("type")
            or "function_call"
        )

        raw_arguments = function_payload.get("arguments") or call_dict.get("arguments")
        parsed_arguments: Any = raw_arguments
        if isinstance(raw_arguments, str):
            try:
                parsed_arguments = json.loads(raw_arguments)
            except ValueError:
                parsed_arguments = raw_arguments

        if isinstance(parsed_arguments, (dict, list)):
            serialized_input = json.dumps(parsed_arguments, sort_keys=True, ensure_ascii=False)
        elif parsed_arguments is None:
            serialized_input = None
        else:
            serialized_input = str(parsed_arguments)

        dedupe_key = (
            str(tool_name) if tool_name is not None else None,
            str(call_id) if call_id is not None else None,
            serialized_input,
        )

        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        tool_input: dict[str, Any] = {
            "name": tool_name,
        }
        if isinstance(parsed_arguments, dict):
            tool_input["arguments"] = parsed_arguments
        elif parsed_arguments is not None:
            tool_input["arguments"] = parsed_arguments

        logger.info(
            "OpenAI function call detected: %s call_id=%s", tool_name, call_id or "<none>"
        )

        await emit_tool_use_event(
            manager=manager,
            provider="openai",
            tool_name=str(tool_name),
            tool_input=tool_input,
            call_id=str(call_id) if call_id else None,
        )
