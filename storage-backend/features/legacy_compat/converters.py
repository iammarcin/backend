"""
Converter functions to transform new API formats to legacy API formats.
"""

from __future__ import annotations

from typing import Any, Dict

from features.chat.schemas.responses import ChatSessionPayload, ChatMessagePayload


def session_to_legacy_format(session: ChatSessionPayload, include_messages: bool = False) -> Dict[str, Any]:
    """
    Convert a ChatSessionPayload to legacy session format.

    Args:
        session: The session object from the new API
        include_messages: Whether to include messages in the output

    Returns:
        Dictionary in legacy session format
    """
    session_dict = {
        "session_id": session.session_id,
        "customer_id": session.customer_id,
        "session_name": session.session_name or "New chat",
        "ai_character_name": session.ai_character_name,
        "tags": session.tags or [],
        "created_at": session.created_at if session.created_at else None,
        "last_update": session.last_update if session.last_update else None,
        "auto_trigger_tts": getattr(session, "auto_trigger_tts", False),
        "ai_text_gen_model": getattr(session, "ai_text_gen_model", ""),
    }

    if include_messages:
        session_dict["messages"] = []
        if hasattr(session, "messages") and session.messages:
            for msg in session.messages:
                session_dict["messages"].append(message_to_legacy_format(msg))

    return session_dict


def message_to_legacy_format(msg: ChatMessagePayload) -> Dict[str, Any]:
    """
    Convert a ChatMessagePayload to legacy message format.

    Args:
        msg: The message object from the new API

    Returns:
        Dictionary in legacy message format
    """
    file_urls = msg.file_locations or []
    return {
        "message_id": msg.message_id,
        "db_message_id": msg.message_id,  # Kotlin expects dbMessageId
        "session_id": msg.session_id,
        "customer_id": msg.customer_id,
        "sender": msg.sender,
        "message": msg.message,
        "image_locations": msg.image_locations or [],
        "file_locations": file_urls,
        "file_names": file_urls,  # Kotlin expects fileNames
        "favorite": getattr(msg, "favorite", False),
        "created_at": msg.created_at if msg.created_at else None,
        "timer_start": None,  # Kotlin expects timerStart
        "timer_end": None,  # Kotlin expects timerEnd
    }


__all__ = ["session_to_legacy_format", "message_to_legacy_format"]
