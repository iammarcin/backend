"""Converters for proactive agent data models.

Converts ChatSession/ChatMessage to proactive agent response format.
"""

from __future__ import annotations

from typing import Any

from features.chat.db_models import ChatMessage, ChatSession


def message_to_dict(
    message: ChatMessage,
    include_reasoning: bool = True,
) -> dict[str, Any]:
    """Convert ChatMessage to proactive agent response format.

    Args:
        message: The ChatMessage model to convert
        include_reasoning: Whether to include ai_reasoning field.
            Set False for real-time WebSocket pushes (reasoning was sent via chunks).
            Set True for session restore/polling (need to load from DB).
    """
    claude_data = message.claude_code_data or {}
    result = {
        "message_id": message.message_id,
        "session_id": message.session_id,
        "direction": claude_data.get("direction", "agent_to_user"),
        "content": message.message,
        "source": claude_data.get("source"),
        "is_heartbeat_ok": claude_data.get("is_heartbeat_ok", False),
        "created_at": message.created_at.isoformat() if message.created_at else None,
        "ai_character_name": message.ai_character_name or "sherlock",
    }
    # Include ai_reasoning only when requested (not during real-time streaming)
    if include_reasoning and message.ai_reasoning:
        result["ai_reasoning"] = message.ai_reasoning
    # Include attachments if present
    if message.image_locations:
        result["image_locations"] = message.image_locations
    if message.file_locations:
        result["file_locations"] = message.file_locations
    return result


def session_to_dict(session: ChatSession) -> dict[str, Any]:
    """Convert ChatSession to proactive agent response format."""
    return {
        "session_id": session.session_id,
        "user_id": session.customer_id,
        "claude_session_id": session.claude_session_id,
        "ai_character_name": session.ai_character_name,
        "is_active": True,  # All sherlock sessions are considered active
        "last_activity": session.last_update.isoformat() if session.last_update else None,
        "created_at": session.created_at.isoformat() if session.created_at else None,
    }


__all__ = ["message_to_dict", "session_to_dict"]
