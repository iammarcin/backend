"""Tool event helpers for the OpenAI Responses API."""

from __future__ import annotations

import logging
from typing import Any, Iterable, Set, Tuple


TOOL_EVENT_KEYWORDS = ("tool", "function", "search")

ALWAYS_ALLOW_EVENT_TYPES = {
    # .added events carry the final web_search payload, so treat them as terminal
    "response.output_item.done",
    "response.output_item.added",
}

from config.text.providers.openai import defaults as openai_defaults
from core.providers.text.utils.responses_tools import (
    _extract_plain_tool_items,
    _serialize_for_seen,
    _to_plain_data,
)
from core.streaming.manager import StreamingManager
from features.chat.services.streaming.events import emit_tool_use_event

logger = logging.getLogger(__name__)

ToolSeenKey = Tuple[str | None, str | None, str | None]


async def emit_tool_events(
    *,
    payload: Any,
    manager: StreamingManager | None,
    seen: Set[ToolSeenKey],
) -> None:
    """Emit tool usage events discovered in Responses API payloads.

    The OpenAI Responses API streams multiple events for a single tool call
    (start → delta → done). We only emit tool events once the call is
    complete to avoid flooding the frontend with partial payloads.
    """

    if manager is None or payload is None:
        return

    event_type = _get_event_type(payload)
    _log_tool_related_event(event_type, payload)

    if not _should_process_event_type(event_type):
        return

    items = list(_iter_tool_items(payload))
    if not items:
        return

    for item in items:
        name = item.get("name") or item.get("tool") or item.get("type")
        call_id = item.get("call_id") or item.get("id")

        if name == "web_search_call":
            name = "web_search"

        tool_input = _extract_tool_input(item)
        if tool_input is None:
            logger.debug(
                "Skipping tool item without completed payload: name=%s call_id=%s",
                name,
                call_id,
            )
            continue

        plain_input = _to_plain_data(tool_input)

        dedupe_key = _build_dedupe_key(name, call_id, plain_input)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        if not name:
            continue

        await emit_tool_use_event(
            manager=manager,
            provider="openai",
            tool_name=str(name),
            tool_input=plain_input,
            call_id=str(call_id) if call_id else None,
        )


def _iter_tool_items(payload: Any) -> Iterable[dict[str, Any]]:
    items = _extract_plain_tool_items(payload)
    return items or []


def _get_event_type(payload: Any) -> str | None:
    if hasattr(payload, "type"):
        return getattr(payload, "type")
    if isinstance(payload, dict):
        return payload.get("type")
    return None


def _extract_tool_input(item: dict[str, Any]) -> Any:
    if item.get("type") == "web_search_call":
        status = item.get("status")
        if status != "completed":
            return None
        action = item.get("action")
        return action if action is not None else {}

    for key in ("input", "arguments", "args", "payload", "web_search", "code_interpreter"):
        if key in item:
            return item[key]
    return {}


def _build_dedupe_key(
    name: str | None,
    call_id: str | None,
    tool_input: Any,
) -> ToolSeenKey:
    normalized_name = str(name) if name is not None else None

    if call_id is not None:
        return (normalized_name, str(call_id), None)

    serialized_input = _serialize_for_seen(tool_input)
    return (
        normalized_name,
        None,
        serialized_input,
    )


def _should_process_event_type(event_type: str | None) -> bool:
    if event_type is None:
        return False

    normalized = event_type.lower()

    if normalized in ALWAYS_ALLOW_EVENT_TYPES:
        return True

    if normalized.endswith((".done", ".completed")):
        return True

    return False


def _log_tool_related_event(event_type: str | None, payload: Any) -> None:
    """Log tool-related events at appropriate verbosity levels."""

    if not event_type:
        return

    lowered = event_type.lower()
    if not any(keyword in lowered for keyword in TOOL_EVENT_KEYWORDS):
        return

    has_items_attr = bool(
        hasattr(payload, "item")
        or hasattr(payload, "items")
        or (
            isinstance(payload, dict)
            and any(key in payload for key in ("item", "items"))
        )
    )
    has_tool_attr = bool(
        hasattr(payload, "tool")
        or hasattr(payload, "tool_call")
        or (
            isinstance(payload, dict)
            and any(key in payload for key in ("tool", "tool_call"))
        )
    )

    is_important_event = lowered.endswith((".added", ".done", ".completed"))

    is_delta_event = ".delta" in lowered

    # Skip .delta events entirely - they fire many times per second and add noise
    # If you need to debug streaming, set VERBOSE_TOOL_LOGGING=true in environment
    if is_delta_event:
        verbose_logging = openai_defaults.VERBOSE_TOOL_LOGGING
        if not verbose_logging:
            return  # Skip logging .delta events by default

    log_method = logger.info if is_important_event else logger.debug
    log_message = (
        "🔍 Responses API tool event: type=%s has_items=%s has_tool=%s"
        if is_important_event
        else "Responses API tool event (streaming): type=%s has_items=%s has_tool=%s"
    )

    log_method(
        log_message,
        event_type,
        has_items_attr,
        has_tool_attr,
    )

    # Only log payload attributes for important events (not every streaming event)
    if is_important_event and hasattr(payload, "__dict__"):
        logger.debug(
            "Responses API event payload attributes: %s",
            list(payload.__dict__.keys()),
        )


__all__ = ["emit_tool_events", "ToolSeenKey"]
