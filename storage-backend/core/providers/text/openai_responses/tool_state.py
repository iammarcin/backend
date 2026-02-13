"""Utilities for tracking tool call state in OpenAI Responses streaming."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict

logger = logging.getLogger(__name__)


@dataclass
class PendingToolCall:
    """Track streamed tool call metadata until completion."""

    name: str | None = None
    call_id: str | None = None
    item_id: str | None = None
    arguments: list[str] = field(default_factory=list)


def get_event_type(event: Any) -> str | None:
    return getattr(event, "type", None) or (
        event.get("type") if isinstance(event, dict) else None
    )


def extract_delta(event: Any) -> str | None:
    delta = getattr(event, "delta", None) or (
        event.get("delta") if isinstance(event, dict) else None
    )
    if delta and isinstance(delta, (str, bytes)):
        return delta if isinstance(delta, str) else delta.decode()
    if hasattr(delta, "text"):
        return getattr(delta, "text")
    return delta if isinstance(delta, str) else None


def capture_tool_metadata(event: Any, pending_calls: Dict[str, PendingToolCall]) -> None:
    item = _get_item(event)
    if not item:
        return

    item_type = getattr(item, "type", None) or (
        item.get("type") if isinstance(item, dict) else None
    )
    if item_type not in {"function_call", "custom_tool_call"}:
        return

    call_id = _read_attr(item, "call_id")
    item_id = _read_attr(item, "id")
    item_name = _read_attr(item, "name")

    if not item_name or not call_id or not item_id:
        logger.warning("Tool metadata incomplete (name=%s call_id=%s item_id=%s)", item_name, call_id, item_id)
        return

    pending_calls[str(item_id)] = PendingToolCall(
        name=item_name,
        call_id=call_id,
        item_id=item_id,
    )

def append_tool_arguments(event: Any, pending_calls: Dict[str, PendingToolCall]) -> None:
    call_id = extract_call_id(event)
    if not call_id:
        return

    chunk = _extract_arguments_chunk(event)
    if not chunk:
        return

    pending_calls.setdefault(call_id, PendingToolCall()).arguments.append(chunk)


def finalise_tool_call(event: Any, pending_calls: Dict[str, PendingToolCall]) -> dict[str, Any] | None:
    item_id = getattr(event, "item_id", None) or (
        event.get("item_id") if isinstance(event, dict) else None
    )

    if not item_id:
        logger.error("response.function_call_arguments.done event has no item_id field")
        return None

    state = pending_calls.pop(item_id, None)
    if not state or not state.name or not state.call_id:
        logger.error("No valid tool metadata for item_id=%s", item_id)
        return None

    raw_arguments = _extract_arguments_value(event)
    if not raw_arguments and state.arguments:
        raw_arguments = "".join(state.arguments)

    parsed_arguments = _parse_arguments(raw_arguments)

    payload = _build_tool_chunk_payload(
        name=state.name,
        call_id=state.call_id,
        item_id=state.item_id,
        arguments=parsed_arguments,
    )

    logger.info(
        "Tool call: %s (call_id=%s, item_id=%s)",
        state.name,
        state.call_id,
        state.item_id,
    )
    return {
        "type": "tool_call",
        "content": payload,
        "requires_action": False,
    }


def extract_call_id(event: Any) -> str | None:
    call_id = getattr(event, "call_id", None)

    if call_id is None and isinstance(event, dict):
        call_id = event.get("call_id")

    if call_id is None:
        item = _get_item(event)
        if item is not None:
            call_id = _read_attr(item, "call_id")

    if call_id is None:
        call_id = getattr(event, "id", None) or getattr(event, "item_id", None)
        if call_id is None and isinstance(event, dict):
            call_id = event.get("id") or event.get("item_id")
        if call_id is None:
            item = _get_item(event)
            if item is not None:
                call_id = _read_attr(item, "id")

    return str(call_id) if call_id is not None else None


def _extract_arguments_chunk(event: Any) -> str | None:
    delta = getattr(event, "delta", None) or (
        event.get("delta") if isinstance(event, dict) else None
    )
    chunk: Any = delta
    if isinstance(delta, dict):
        chunk = delta.get("arguments") or delta.get("text")
    if chunk is None:
        chunk = getattr(event, "arguments", None)
        if chunk is None and isinstance(event, dict):
            chunk = event.get("arguments")
    if isinstance(chunk, bytes):
        return chunk.decode()
    if isinstance(chunk, str) and chunk:
        return chunk
    return None


def _extract_arguments_value(event: Any) -> Any:
    if hasattr(event, "arguments"):
        return getattr(event, "arguments")
    if isinstance(event, dict) and "arguments" in event:
        return event.get("arguments")
    return None


def _parse_arguments(arguments: Any) -> Any:
    if isinstance(arguments, str):
        stripped = arguments.strip()
        if not stripped:
            return {}
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return {"raw": stripped}
    return arguments if arguments is not None else {}


def _build_tool_chunk_payload(
    *, name: str, call_id: str | None, item_id: str | None, arguments: Any
) -> dict[str, Any]:
    tool_input = arguments if isinstance(arguments, dict) else {"value": arguments}
    return {
        "name": name,
        "toolName": name,
        "input": tool_input,
        "toolInput": tool_input,
        "id": call_id,
        "callId": call_id,
        "itemId": item_id,
        "provider": "openai",
    }


def _get_item(event: Any) -> Any:
    if hasattr(event, "item"):
        return getattr(event, "item")
    if isinstance(event, dict):
        return event.get("item")
    return None


def _read_attr(obj: Any, attr: str) -> Any:
    value = getattr(obj, attr, None)
    if value is None and isinstance(obj, dict):
        value = obj.get(attr)
    return value


__all__ = [
    "PendingToolCall",
    "append_tool_arguments",
    "capture_tool_metadata",
    "extract_delta",
    "finalise_tool_call",
    "get_event_type",
    "extract_call_id",
]
