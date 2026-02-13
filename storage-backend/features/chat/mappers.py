"""Serialiser helpers for chat ORM models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from features.chat.db_models import ChatMessage, ChatSession, Prompt, User


def _normalise_datetime(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return value.isoformat()


def _normalise_json(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    return value


def _ensure_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, dict)):
        return list(value)
    return [value]


def chat_message_to_dict(message: ChatMessage) -> dict[str, Any]:
    """Return a serialisable representation of a chat message."""

    return {
        "message_id": message.message_id,
        "session_id": message.session_id,
        "customer_id": message.customer_id,
        "sender": message.sender,
        "message": message.message,
        "ai_reasoning": message.ai_reasoning,
        "image_locations": _ensure_list(_normalise_json(message.image_locations, [])),
        "image_description": getattr(message, "image_description", None),
        "file_locations": _ensure_list(_normalise_json(message.file_locations, [])),
        "chart_data": _normalise_json(message.chart_data, None),
        "ai_character_name": message.ai_character_name or "",
        "is_tts": bool(message.is_tts),
        "api_text_gen_model_name": message.api_text_gen_model_name or "",
        "api_text_gen_settings": dict(_normalise_json(message.api_text_gen_settings, {})),
        "api_tts_gen_model_name": message.api_tts_gen_model_name or "",
        "api_image_gen_settings": dict(_normalise_json(message.api_image_gen_settings, {})),
        "image_generation_request": dict(_normalise_json(message.image_generation_request, {})),
        "claude_code_data": dict(_normalise_json(message.claude_code_data, {})),
        "is_gps_location_message": bool(message.is_gps_location_message),
        "show_transcribe_button": bool(message.show_transcribe_button),
        "favorite": bool(message.favorite),
        "test_mode": bool(message.test_mode),
        "created_at": _normalise_datetime(message.created_at),
    }


def chat_session_to_dict(
    session: ChatSession,
    *,
    include_messages: bool = False,
    group_name: str | None = None,
) -> dict[str, Any]:
    """Return a serialisable representation of a chat session.

    Args:
        session: The ChatSession ORM model to serialize.
        include_messages: If True, include all messages in the output.
        group_name: Optional group name to include (avoids extra query when already known).
    """

    session_dict = {
        "session_id": session.session_id,
        "customer_id": session.customer_id,
        "session_name": session.session_name,
        "ai_character_name": session.ai_character_name,
        "ai_text_gen_model": session.ai_text_gen_model,
        "auto_trigger_tts": bool(session.auto_trigger_tts),
        "claude_session_id": session.claude_session_id,
        "tags": list(_normalise_json(session.tags, [])),
        "created_at": _normalise_datetime(session.created_at),
        "last_update": _normalise_datetime(session.last_update),
        # Group info for group chat sessions
        "group_id": str(session.group_id) if session.group_id else None,
        "group_name": group_name,
        # Task metadata
        "task_status": session.task_status,
        "task_priority": session.task_priority,
        "task_description": session.task_description,
    }

    if include_messages:
        session_dict["messages"] = [chat_message_to_dict(message) for message in session.messages]

    return session_dict


def prompt_to_dict(prompt: Prompt) -> dict[str, Any]:
    """Return a serialisable representation of a prompt."""

    return {
        "prompt_id": prompt.prompt_id,
        "customer_id": prompt.customer_id,
        "title": prompt.title,
        "prompt": prompt.prompt,
    }


def user_to_dict(user: User) -> dict[str, Any]:
    """Return a serialisable representation of a user."""

    return {
        "customer_id": user.customer_id,
        "username": user.username,
        "email": user.email,
        "created_at": _normalise_datetime(user.created_at),
    }


__all__ = [
    "chat_message_to_dict",
    "chat_session_to_dict",
    "prompt_to_dict",
    "user_to_dict",
]
