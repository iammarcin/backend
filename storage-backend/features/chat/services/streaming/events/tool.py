"""Tool usage event helpers and formatting utilities."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from core.streaming.manager import StreamingManager


logger = logging.getLogger(__name__)


async def emit_tool_use_event(
    manager: StreamingManager,
    *,
    provider: str,
    tool_name: str,
    tool_input: Dict[str, Any] | None = None,
    call_id: str | None = None,
    metadata: Dict[str, Any] | None = None,
    session_id: Optional[str] = None,
) -> None:
    """Emit a tool_start event for frontend tool display.

    Frontend schema expects:
    {
        "type": "tool_start",
        "data": {
            "tool_name": str,
            "tool_input": dict (optional),
            "display_text": str (optional),
            "session_id": str
        }
    }
    """

    if not tool_name:
        logger.debug("Skipping tool event emission because tool_name is missing")
        return

    normalised_input = tool_input or {}

    display_text = _generate_tool_display_text(
        tool_name=tool_name,
        tool_input=normalised_input,
    )

    # Build data payload matching frontend ToolStartEventSchema
    data: Dict[str, Any] = {
        "tool_name": tool_name,
        "display_text": display_text,
    }
    if normalised_input:
        data["tool_input"] = normalised_input
    if session_id:
        data["session_id"] = session_id
    if call_id:
        data["call_id"] = call_id
    if metadata:
        data["metadata"] = metadata
    # Include provider for debugging
    data["provider"] = provider

    logger.debug(
        "Emitting tool_start event: provider=%s tool=%s call_id=%s", provider, tool_name, call_id
    )

    send_to_queues = getattr(manager, "send_to_queues", None)
    if send_to_queues is None:
        logger.debug(
            "Streaming manager missing send_to_queues; skipping tool_start dispatch"
        )
        return

    # Send tool_start directly - frontend dispatcher handles this type
    await send_to_queues(
        {
            "type": "tool_start",
            "data": data,
        }
    )


def _generate_tool_display_text(tool_name: str, tool_input: Dict[str, Any]) -> str:
    """Generate human-readable display text for tool usage."""

    emoji = _get_tool_emoji(tool_name)
    snippet = _extract_tool_snippet(tool_name, tool_input)

    if not snippet:
        return f"{emoji} {tool_name}"

    return f"{emoji} {tool_name}: {snippet}"


def _get_tool_emoji(tool_name: str) -> str:
    """Return an emoji representing the tool type."""

    tool_emoji_map = {
        "web_search": "🔍",
        "google_search": "🌐",
        "google_search_retrieval": "🌐",
        "code_interpreter": "💻",
        "code_execution": "⚡",
        "bash_execution": "⚙️",
        "function_call": "🧩",
    }

    return tool_emoji_map.get(tool_name, "🛠️")


def _extract_tool_snippet(
    tool_name: str,
    tool_input: Dict[str, Any],
    max_length: int = 100,
) -> str:
    """Extract a displayable snippet from the tool input."""

    if not isinstance(tool_input, dict):
        if tool_input is None:
            return ""
        return _truncate_text(str(tool_input), max_length)

    if tool_name in {"web_search", "google_search", "google_search_retrieval"}:
        query = (
            tool_input.get("query")
            or tool_input.get("search_query")
            or tool_input.get("q")
            or ""
        )
        if isinstance(query, str):
            return _truncate_text(query.strip(), max_length)

    if tool_name in {"code_interpreter", "code_execution"}:
        code = (
            tool_input.get("code")
            or tool_input.get("input")
            or tool_input.get("instructions")
            or ""
        )
        if isinstance(code, str):
            first_line = code.split("\n")[0].strip()
            return _truncate_text(first_line, max_length)

    if tool_name == "function_call":
        func_name = tool_input.get("name", "unknown")
        args = tool_input.get("arguments") or tool_input.get("input") or {}
        if isinstance(args, dict) and args:
            preview_parts = []
            for key, value in list(args.items())[:3]:
                preview_parts.append(f"{key}={repr(value)[:20]}")
            args_str = ", ".join(preview_parts)
            return f"{func_name}({args_str})"
        return str(func_name)

    if "name" in tool_input and "input" in tool_input:
        name = tool_input.get("name")
        input_data = tool_input.get("input")
        if isinstance(name, str) and isinstance(input_data, dict):
            preview_parts = []
            for key, value in list(input_data.items())[:3]:
                preview_parts.append(f"{key}={repr(value)[:20]}")
            args_str = ", ".join(preview_parts)
            return f"{name}({args_str})" if args_str else name

    try:
        text = json.dumps(tool_input, ensure_ascii=False)
    except (TypeError, ValueError):
        text = str(tool_input)

    return _truncate_text(text, max_length)


def _truncate_text(text: str, max_length: int) -> str:
    """Truncate text and append ellipsis when needed."""

    if len(text) <= max_length:
        return text
    return text[:max_length] + "…"


__all__ = [
    "emit_tool_use_event",
    "_generate_tool_display_text",
    "_get_tool_emoji",
    "_extract_tool_snippet",
]
