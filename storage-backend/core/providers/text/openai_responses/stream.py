"""Streaming helpers for the OpenAI Responses API."""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator, Dict, List, Sequence, Set

from core.exceptions import ProviderError, RateLimitError
from core.providers.registry.model_config import ModelConfig
from core.providers.text.responses_utils import build_responses_params
from core.providers.text.utils import log_responses_tool_calls
from core.streaming.manager import StreamingManager

from .tool_events import ToolSeenKey, emit_tool_events
from .tool_state import (
    PendingToolCall,
    append_tool_arguments,
    capture_tool_metadata,
    extract_delta,
    finalise_tool_call,
    get_event_type,
)

logger = logging.getLogger(__name__)


def _extract_reasoning_text(item: Any) -> str | None:
    """Normalize reasoning summaries from output items."""

    summary = getattr(item, "summary", None)
    if summary is None and isinstance(item, dict):
        summary = item.get("summary")

    def _collapse_sequence(values: Sequence[Any]) -> str:
        return " ".join(str(value) for value in values if value not in {None, ""})

    if summary:
        if isinstance(summary, (list, tuple)):
            return _collapse_sequence(summary)
        return str(summary)

    content = getattr(item, "content", None)
    if content is None and isinstance(item, dict):
        content = item.get("content")

    if isinstance(content, (list, tuple)):
        parts: list[str] = []
        for content_item in content:
            text_value = getattr(content_item, "text", None)
            if text_value is None and isinstance(content_item, dict):
                text_value = content_item.get("text") or content_item.get("content")
            if text_value:
                parts.append(str(text_value))
        if parts:
            return " ".join(parts)

    text_attr = getattr(item, "text", None)
    if text_attr:
        return str(text_attr)

    return None


async def stream_responses_api(
    *,
    client: Any,
    model_config: ModelConfig | None,
    messages: list[dict[str, Any]],
    model: str,
    temperature: float,
    max_tokens: int,
    manager: StreamingManager | None = None,
    enable_reasoning: bool,
    **kwargs: Any,
) -> AsyncIterator[str | dict[str, Any]]:
    """Stream chunks from the OpenAI Responses API."""

    tools = kwargs.pop("tools", None)

    params = build_responses_params(
        model=model,
        messages=messages,
        model_config=model_config,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
        extra_kwargs=kwargs,
        enable_reasoning=enable_reasoning,
        tools=tools,
    )

    tool_names: list[str] = []
    if tools:
        tool_names = [
            tool.get("function", {}).get("name")
            if "function" in tool
            else tool.get("name")
            or tool.get("type")
            for tool in tools
        ]

    logger.info(
        "Calling OpenAI Responses API: model=%s tools=%d messages=%d | tool_names=%s",
        params.get("model"),
        len(params.get("tools", [])),
        len(params.get("input", [])),
        tool_names if tool_names else "none",
    )
    logger.debug(
        "OpenAI Responses API params: temperature=%s max_tokens=%s reasoning=%s",
        params.get("temperature"),
        params.get("max_output_tokens"),
        params.get("reasoning"),
    )

    try:
        response_stream = await client.responses.create(**params)
    except Exception as exc:  # pragma: no cover - handled below
        error_msg = str(exc)
        if "rate limit" in error_msg.lower():
            raise RateLimitError(f"OpenAI rate limit: {error_msg}") from exc

        logger.error("OpenAI Responses API stream error: %s", exc)
        raise ProviderError(
            f"OpenAI Responses API streaming error: {error_msg}",
            provider="openai",
            original_error=exc,
        ) from exc

    seen_tool_calls: Set[ToolSeenKey] = set()
    pending_calls: Dict[str, PendingToolCall] = {}

    emitted_reasoning_chunk = False

    async for event in response_stream:
        await emit_tool_events(
            payload=event,
            manager=manager,
            seen=seen_tool_calls,
        )

        log_responses_tool_calls(
            event,
            source="stream",
            seen=seen_tool_calls,
            logger=logger,
        )

        event_type = get_event_type(event)
        if event_type in {
            "response.error",
        }:
            logger.debug("Responses API event: type=%s", event_type)

        # Check for reasoning items in output_item events
        if event_type == "response.output_item.added":
            # Check if this is a reasoning item
            item = getattr(event, "item", None)
            if item:
                item_type = getattr(item, "type", None)
                logger.debug("🔍 output_item.added: item_type=%s", item_type)

                if item_type == "reasoning":
                    logger.info("✅ OpenAI reasoning item: %s", item)
                    reasoning_text = _extract_reasoning_text(item)
                    if reasoning_text:
                        logger.info("✅ OpenAI reasoning from output_item: %s", reasoning_text[:100])
                        emitted_reasoning_chunk = True
                        yield {"type": "reasoning", "content": reasoning_text}
                        continue

            # Not a reasoning item, handle as tool metadata
            capture_tool_metadata(event, pending_calls)
            continue

        if event_type == "response.function_call_arguments.delta":
            append_tool_arguments(event, pending_calls)
            continue

        if event_type == "response.function_call_arguments.done":
            chunk = finalise_tool_call(event, pending_calls)
            if chunk:
                logger.info(
                    "✅ Tool call finalized and ready to yield: name=%s call_id=%s",
                    chunk.get("content", {}).get("toolName"),
                    chunk.get("content", {}).get("callId"),
                )
                yield chunk
            else:
                logger.error(
                    "❌ Tool call finalization failed! event_type=%s",
                    event_type,
                )
            continue

        if event_type in {
            "response.output_text.delta",
            "response.text.delta",
            "response.delta",
        }:
            delta = extract_delta(event)
            if delta:
                yield delta
            continue

        # Handle reasoning summary from Responses API (only summaries are provided)
        # Event types: response.reasoning_summary_text.delta/.done, response.reasoning_summary.delta
        if event_type in {
            "response.reasoning_summary_text.delta",
            "response.reasoning_summary.delta",
            "response.reasoning_summary_text.done",
        }:
            delta = extract_delta(event)

            # Fallback to direct attribute access if helper failed
            if not delta and hasattr(event, "delta"):
                delta = getattr(event, "delta")

            # Some events expose text attribute (e.g. _text events)
            if not delta and hasattr(event, "text"):
                delta = getattr(event, "text")

            # Final summaries may live on summary attribute
            if not delta and hasattr(event, "summary"):
                delta = getattr(event, "summary")

            is_done_event = event_type.endswith(".done")
            if delta and (not is_done_event or not emitted_reasoning_chunk):
                emitted_reasoning_chunk = True
                yield {"type": "reasoning", "content": str(delta)}
                continue
            if is_done_event:
                logger.debug(
                    "Reasoning summary done event ignored (delta=%s, emitted=%s)",
                    bool(delta),
                    emitted_reasoning_chunk,
                )
            else:
                logger.warning(
                    "⚠️ OpenAI reasoning event but no delta found: event_type=%s attrs=%s",
                    event_type,
                    dir(event),
                )
            continue

        if event_type in {
            "response.completed",
            "response.output_text.done",
            "response.stream.completed",
        }:
            # Log finish_reason and usage for debugging truncation issues
            if event_type == "response.completed":
                response_obj = getattr(event, "response", None) or (
                    event.get("response") if isinstance(event, dict) else None
                )
                if response_obj:
                    finish_reason = getattr(response_obj, "status", None) or (
                        response_obj.get("status") if isinstance(response_obj, dict) else None
                    )
                    usage = getattr(response_obj, "usage", None) or (
                        response_obj.get("usage") if isinstance(response_obj, dict) else None
                    )
                    if finish_reason == "incomplete":
                        incomplete_details = getattr(response_obj, "incomplete_details", None) or (
                            response_obj.get("incomplete_details") if isinstance(response_obj, dict) else None
                        )
                        logger.warning(
                            "⚠️ Responses API stream incomplete: status=%s reason=%s usage=%s",
                            finish_reason,
                            incomplete_details,
                            usage,
                        )
                    else:
                        logger.info(
                            "Responses API stream completed: status=%s usage=%s",
                            finish_reason,
                            usage,
                        )
            continue

        if event_type == "response.error":
            error = getattr(event, "error", None) or (
                event.get("error") if isinstance(event, dict) else "unknown error"
            )
            raise ProviderError(
                f"Responses API error: {error}",
                provider="openai",
            )

__all__ = ["stream_responses_api"]
