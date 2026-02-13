"""
Handler functions for legacy /api/db endpoint actions.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi.responses import JSONResponse

from features.chat.schemas.requests import (
    CreateMessageRequest,
    SessionDetailRequest,
    SessionListRequest,
    SessionSearchRequest,
)
from features.chat.schemas.message_content import MessageContent
from features.chat.service import ChatHistoryService
from .converters import session_to_legacy_format
from .response_helpers import legacy_error_response, legacy_success_response

logger = logging.getLogger(__name__)


async def handle_db_search_messages(
    customer_id: int,
    user_input: Dict[str, Any],
    service: ChatHistoryService,
) -> JSONResponse:
    """
    Handle db_search_messages action.

    Legacy: Search messages or list sessions
    Maps to: SessionSearchRequest
    """
    search_text = user_input.get("search_text", "")

    search_request = SessionSearchRequest(
        customer_id=customer_id,
        search_text=search_text,
        limit=30
    )

    result = await service.search_sessions(search_request)

    # Convert to legacy format (list of sessions without messages)
    sessions_list = [
        session_to_legacy_format(session, include_messages=False)
        for session in result.sessions
    ]

    return legacy_success_response(sessions_list)


async def handle_db_all_sessions_for_user(
    customer_id: int,
    user_input: Dict[str, Any],
    service: ChatHistoryService,
) -> JSONResponse:
    """
    Handle db_all_sessions_for_user action.

    Legacy: Get all sessions for user with filters
    Maps to: SessionListRequest
    """
    offset = user_input.get("offset", 0)
    limit = user_input.get("limit", 100)
    tags = user_input.get("tags", [])
    start_date = user_input.get("start_date")
    end_date = user_input.get("end_date")

    list_request = SessionListRequest(
        customer_id=customer_id,
        offset=offset,
        limit=limit,
        tags=tags,
        start_date=start_date,
        end_date=end_date,
        include_messages=True  # Include messages for legacy compatibility
    )

    result = await service.list_sessions(list_request)

    # Convert to legacy format
    sessions_list = [
        session_to_legacy_format(session, include_messages=True)
        for session in result.sessions
    ]

    return legacy_success_response(sessions_list)


async def handle_db_get_user_session(
    customer_id: int,
    user_input: Dict[str, Any],
    service: ChatHistoryService,
) -> JSONResponse:
    """
    Handle db_get_user_session action.

    Legacy: Get session details with messages
    Maps to: SessionDetailRequest
    """
    session_id = user_input.get("session_id")
    ai_character = user_input.get("ai_character")

    if not session_id and not ai_character:
        return legacy_error_response("Either session_id or ai_character must be provided", 400)

    detail_request = SessionDetailRequest(
        customer_id=customer_id,
        session_id=session_id,
        ai_character_name=ai_character
    )

    result = await service.get_session(detail_request)

    # Convert to legacy format
    session_dict = session_to_legacy_format(result.session, include_messages=True)

    return legacy_success_response(session_dict)


async def handle_db_new_message(
    customer_id: int,
    user_input: Dict[str, Any],
    user_settings: Dict[str, Any],
    service: ChatHistoryService,
) -> JSONResponse:
    """
    Handle db_new_message action.

    Legacy: Create new message(s) in a session
    Maps to: CreateMessageRequest
    """
    session_id = user_input.get("session_id", "")
    # Note: After camelCase→snake_case conversion, keys are snake_case
    user_message = user_input.get("user_message", {})
    ai_response = user_input.get("ai_response")
    auto_trigger_tts = user_input.get("auto_trigger_tts", False)
    ai_text_gen_model = user_input.get("ai_text_gen_model", "")
    new_ai_character_name = user_input.get("new_ai_character_name", "assistant")

    # Extract text settings for ai_character fallback
    text_settings = user_settings.get("text", {})
    if not new_ai_character_name or new_ai_character_name == "assistant":
        new_ai_character_name = text_settings.get("ai_character", "assistant")

    # Build user message content
    # Note: Legacy mobile sends fileNames → file_names after camelCase conversion
    # We map it to file_locations for the MessageContent schema
    user_msg_content = MessageContent(
        sender="User",
        message=user_message.get("message", ""),
        image_locations=user_message.get("image_locations", []),
        file_locations=user_message.get("file_names", []),
        is_gps_location_message=user_message.get("is_gps_location_message", False),
    )

    # Build AI response content if present
    # Note: Legacy mobile sends fileNames → file_names after camelCase conversion
    ai_msg_content = None
    if ai_response and ai_response.get("message"):
        ai_msg_content = MessageContent(
            sender="AI",
            message=ai_response.get("message", ""),
            image_locations=ai_response.get("image_locations", []),
            file_locations=ai_response.get("file_names", []),
        )

    create_request = CreateMessageRequest(
        customer_id=customer_id,
        session_id=session_id if session_id else None,
        ai_character_name=new_ai_character_name if not session_id else None,
        session_name=None,  # Will use default "New chat"
        user_message=user_msg_content,
        ai_response=ai_msg_content,
        auto_trigger_tts=auto_trigger_tts,
        ai_text_gen_model=ai_text_gen_model if ai_text_gen_model else None,
    )

    result = await service.create_message(create_request)

    # Convert to legacy format
    response_data = {
        "session_id": result.messages.session_id,
        "user_message_id": result.messages.user_message_id,
        "ai_message_id": result.messages.ai_message_id if result.messages.ai_message_id else 0,
    }

    return legacy_success_response(response_data)


__all__ = [
    "handle_db_search_messages",
    "handle_db_all_sessions_for_user",
    "handle_db_get_user_session",
    "handle_db_new_message",
]
