"""Tool execution handlers for proactive agent (tool start/result)."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from core.connections import get_proactive_registry
from features.proactive_agent.utils.tool_display import format_tool_display_text

logger = logging.getLogger(__name__)


async def handle_tool_start(
    session: Any,
    user_id: int,
    tool_name: Optional[str],
    tool_input: Optional[Dict[str, Any]],
    ai_character_name: str,
) -> bool:
    """Handle tool_start event - push tool execution start.

    Returns True if WebSocket push succeeded.
    """
    registry = get_proactive_registry()
    display_text = format_tool_display_text(tool_name, tool_input, is_complete=False)

    logger.info(
        "[DEBUG] handle_tool_start called: session=%s tool=%s",
        session.session_id,
        tool_name,
    )

    result = await registry.push_to_user(
        user_id=user_id,
        message={
            "type": "tool_start",
            "data": {
                "session_id": session.session_id,
                "tool_name": tool_name,
                "tool_input": tool_input,
                "display_text": display_text,
                "ai_character_name": ai_character_name,
            },
        },
    )
    logger.info("[DEBUG] tool_start pushed: result=%s tool=%s", result, tool_name)
    return result


async def handle_tool_result(
    session: Any,
    user_id: int,
    tool_name: Optional[str],
    tool_input: Optional[Dict[str, Any]],
    tool_result: Optional[str],
    ai_character_name: str,
) -> bool:
    """Handle tool_result event - push tool execution result.

    Returns True if WebSocket push succeeded.
    """
    registry = get_proactive_registry()
    display_text = format_tool_display_text(tool_name, tool_input, is_complete=True)

    logger.info(
        "Tool execution completed: %s (%s)",
        tool_name,
        display_text,
        extra={
            "session_id": session.session_id,
            "user_id": user_id,
            "tool_name": tool_name,
        },
    )

    return await registry.push_to_user(
        user_id=user_id,
        message={
            "type": "tool_result",
            "data": {
                "session_id": session.session_id,
                "tool_name": tool_name,
                "tool_input": tool_input,
                "tool_result": tool_result,
                "display_text": display_text,
                "ai_character_name": ai_character_name,
            },
        },
    )


__all__ = ["handle_tool_start", "handle_tool_result"]
