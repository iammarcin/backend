"""Field mapping helpers for chat message payloads."""

from __future__ import annotations

from typing import Any

from features.chat.db_models import ChatMessage


def create_message_from_payload(
    *,
    session_id: str,
    customer_id: int,
    payload: dict[str, Any],
    is_ai_message: bool,
    claude_code_data: dict[str, Any] | None = None,
) -> ChatMessage:
    """Create a ChatMessage instance from a payload dictionary.

    Args:
        session_id: Chat session identifier
        customer_id: Customer identifier
        payload: Dictionary containing message fields (snake_case keys)
        is_ai_message: Whether this is an AI-generated message
        claude_code_data: Optional Claude Code metadata

    Returns:
        ChatMessage instance with fields populated from payload
    """
    sender = payload.get("sender") or ("AI" if is_ai_message else "User")
    message_obj = ChatMessage(
        session_id=session_id,
        customer_id=customer_id,
        sender=sender,
        message=payload.get("message"),
        ai_reasoning=payload.get("ai_reasoning"),
        image_locations=payload.get("image_locations"),
        file_locations=payload.get("file_locations"),
        chart_data=payload.get("chart_data"),
        ai_character_name=payload.get("ai_character_name"),
        api_text_gen_model_name=payload.get("api_text_gen_model_name") if is_ai_message else None,
        api_text_gen_settings=payload.get("api_text_gen_settings") if is_ai_message else None,
        api_tts_gen_model_name=payload.get("api_tts_gen_model_name") if is_ai_message else None,
        api_image_gen_settings=payload.get("api_image_gen_settings") if is_ai_message else None,
        image_generation_request=payload.get("image_generation_request") if is_ai_message else None,
        claude_code_data=claude_code_data or payload.get("claude_code_data"),
        is_tts=bool(payload.get("is_tts", False)),
        is_gps_location_message=bool(payload.get("is_gps_location_message", False)),
        test_mode=bool(payload.get("test_mode", False)),
        show_transcribe_button=bool(payload.get("show_transcribe_button", False)),
        favorite=bool(payload.get("favorite", False)),
    )

    return message_obj


def update_message_fields(message: ChatMessage, payload: dict[str, Any], append_image_locations: bool = False) -> None:
    """Update message object fields from payload dictionary.

    Args:
        message: ChatMessage instance to update
        payload: Dictionary containing fields to update (snake_case keys)
        append_image_locations: If True, append to existing image locations instead of replacing

    Modifies message object in-place.
    """
    for key, value in payload.items():
        if key == "message":
            message.message = value
        elif key == "ai_reasoning":
            message.ai_reasoning = value
        elif key == "image_locations":
            if append_image_locations and message.image_locations:
                message.image_locations = list(message.image_locations) + list(value)
            else:
                message.image_locations = list(value)
        elif key == "file_locations":
            message.file_locations = list(value)
        elif key == "api_text_gen_model_name":
            message.api_text_gen_model_name = value
        elif key == "api_text_gen_settings":
            message.api_text_gen_settings = value
        elif key == "api_tts_gen_model_name":
            message.api_tts_gen_model_name = value
        elif key == "api_image_gen_settings":
            message.api_image_gen_settings = value
        elif key == "image_generation_request":
            message.image_generation_request = value
        elif key == "claude_code_data":
            message.claude_code_data = value
        elif key == "favorite":
            message.favorite = bool(value)
        elif key == "chart_data":
            message.chart_data = value
