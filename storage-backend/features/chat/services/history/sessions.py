"""Session management routines extracted from the chat history service."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from core.exceptions import DatabaseError, ValidationError

from features.chat.schemas.requests import (
    CreateTaskRequest,
    RemoveSessionRequest,
    SessionDetailRequest,
    SessionListRequest,
    SessionSearchRequest,
    UpdateSessionRequest,
)
from features.chat.schemas.responses import (
    ChatSessionPayload,
    MessagesRemovedResult,
    SessionDetailResult,
    SessionListResult,
)

from features.chat.mappers import chat_session_to_dict
from features.chat.schemas.message_content import MessageContent

from .base import HistoryRepositories, load_session_payload
from .semantic_indexing import queue_semantic_deletion_tasks

logger = logging.getLogger(__name__)


async def list_sessions(
    repositories: HistoryRepositories, request: SessionListRequest
) -> SessionListResult:
    """Return a filtered list of chat sessions."""

    sessions = await repositories.sessions.list_sessions(
        customer_id=request.customer_id,
        start_date=request.start_date,
        end_date=request.end_date,
        tags=request.tags,
        ai_character_name=request.ai_character_name,
        task_status=request.task_status,
        task_priority=request.task_priority,
        offset=request.offset,
        limit=request.limit,
        include_messages=request.include_messages,
    )
    items = [ChatSessionPayload.model_validate(session) for session in sessions]
    return SessionListResult(sessions=items, count=len(items))


async def get_session(
    repositories: HistoryRepositories, request: SessionDetailRequest
) -> SessionDetailResult:
    """Fetch a single session by ID or AI character name."""

    if not (request.session_id or request.ai_character_name):
        raise ValidationError(
            "Either session_id or ai_character_name must be provided",
            field="session_id",
        )

    if request.session_id:
        payload = await load_session_payload(
            repositories,
            request.session_id,
            customer_id=request.customer_id,
            include_messages=request.include_messages,
        )
    else:
        session_obj = await repositories.sessions.get_or_create_for_character(
            customer_id=request.customer_id,
            ai_character_name=request.ai_character_name or "assistant",
        )
        payload = await load_session_payload(
            repositories,
            session_obj.session_id,
            customer_id=request.customer_id,
            include_messages=request.include_messages,
        )
    return SessionDetailResult(session=payload)


async def search_sessions(
    repositories: HistoryRepositories, request: SessionSearchRequest
) -> SessionListResult:
    """Search sessions by fuzzy text criteria."""

    sessions = await repositories.sessions.search_sessions(
        customer_id=request.customer_id,
        search_text=request.search_text,
        limit=request.limit,
    )
    items = [ChatSessionPayload.model_validate(session) for session in sessions]
    return SessionListResult(sessions=items, count=len(items))


async def update_session(
    repositories: HistoryRepositories, request: UpdateSessionRequest
) -> SessionDetailResult:
    """Update session metadata fields."""

    session_obj = await repositories.sessions.update_session_metadata(
        session_id=request.session_id,
        customer_id=request.customer_id,
        session_name=request.session_name,
        ai_character_name=request.ai_character_name,
        auto_trigger_tts=request.auto_trigger_tts,
        ai_text_gen_model=request.ai_text_gen_model,
        tags=request.tags,
        claude_session_id=request.claude_session_id,
        update_last_mod_time=request.update_last_mod_time,
        last_update_override=request.last_update_override,
        task_status=request.task_status,
        task_priority=request.task_priority,
        task_description=request.task_description,
        clear_task_metadata=request.clear_task_metadata,
    )
    session_dict = chat_session_to_dict(session_obj, include_messages=False)
    return SessionDetailResult(
        session=ChatSessionPayload.model_validate(session_dict)
    )


async def remove_session(
    repositories: HistoryRepositories, request: RemoveSessionRequest
) -> MessagesRemovedResult:
    """Delete a session and its messages."""

    success, message_ids = await repositories.sessions.delete_session(
        session_id=request.session_id,
        customer_id=request.customer_id,
    )
    if not success:
        raise DatabaseError("Session not found", operation="delete_session")

    # Delete messages from Qdrant message-level indexes
    if message_ids:
        await queue_semantic_deletion_tasks(message_ids=message_ids)

    # Delete session summary from Qdrant session-level index
    from features.chat.services.history.semantic_indexing import (
        delete_session_summary_from_index,
    )

    await delete_session_summary_from_index(
        session_id=request.session_id, customer_id=request.customer_id
    )

    return MessagesRemovedResult(
        removed_count=len(message_ids),
        message_ids=message_ids or None,
        session_id=request.session_id,
    )


async def create_task(
    repositories: HistoryRepositories, request: CreateTaskRequest
) -> SessionDetailResult:
    """Create a new session promoted to a task in a single transaction."""

    session_name = request.session_name or request.task_description

    session_obj = await repositories.sessions.create_session(
        customer_id=request.customer_id,
        session_name=session_name,
        ai_character_name=request.ai_character_name,
    )

    session_obj.task_status = "active"
    session_obj.task_priority = request.task_priority
    session_obj.task_description = request.task_description

    session_dict = chat_session_to_dict(session_obj, include_messages=False)
    return SessionDetailResult(
        session=ChatSessionPayload.model_validate(session_dict)
    )


async def fork_session_from_history(
    repositories: HistoryRepositories,
    customer_id: int,
    chat_history: List[Dict[str, Any]],
    session_name: str = "New session from here",
    ai_character_name: str = "assistant",
    ai_text_gen_model: str | None = None,
    claude_code_data: Dict[str, Any] | None = None,
) -> str:
    """Create a new session and populate it with historical messages.

    This implements the "New session from here" feature, which allows users
    to fork a chat session at a specific point, creating a new session with
    all messages up to that point.

    Args:
        repositories: Repository bundle for database operations
        customer_id: ID of the customer creating the session
        chat_history: List of historical chat messages to import
        session_name: Name for the new session
        ai_character_name: AI character to use for the session
        ai_text_gen_model: Text generation model name
        claude_code_data: Optional Claude Code metadata

    Returns:
        The session_id of the newly created session
    """
    if not chat_history:
        logger.warning("Empty chat history provided for session fork")
        raise ValidationError("Chat history cannot be empty", field="chat_history")

    logger.info(
        "Forking session with %d historical messages for customer %s",
        len(chat_history),
        customer_id,
    )

    # Create the new session
    session_obj = await repositories.sessions.create_session(
        customer_id=customer_id,
        session_name=session_name,
        ai_character_name=ai_character_name,
        ai_text_gen_model=ai_text_gen_model,
    )
    new_session_id = session_obj.session_id

    logger.debug("Created new session %s for forking", new_session_id)

    # Import each historical message into the new session
    for idx, message_data in enumerate(chat_history):
        is_user_message = message_data.get("is_user_message", True)

        # Build MessageContent from the historical data
        message_content = MessageContent(
            message=message_data.get("message", ""),
            sender="User" if is_user_message else "AI",
            image_locations=message_data.get("image_locations", []),
            file_locations=message_data.get("file_locations", []),
            ai_character_name=message_data.get("ai_character_name", ""),
            api_text_gen_model_name=message_data.get("api_text_gen_model_name", ""),
            api_tts_gen_model_name=message_data.get("api_tts_gen_model_name", ""),
            api_image_gen_settings=message_data.get("api_image_gen_settings", {}),
            is_tts=message_data.get("is_tts", False),
            is_gps_location_message=message_data.get("is_gps_location_message", False),
        )

        # Insert the message
        await repositories.messages.insert_message(
            session_id=new_session_id,
            customer_id=customer_id,
            payload=message_content.to_payload(),
            is_ai_message=not is_user_message,
            claude_code_data=claude_code_data,
        )

        logger.debug(
            "Imported message %d/%d (%s) into session %s",
            idx + 1,
            len(chat_history),
            "user" if is_user_message else "AI",
            new_session_id,
        )

    logger.info(
        "Successfully forked session %s with %d messages for customer %s",
        new_session_id,
        len(chat_history),
        customer_id,
    )

    return new_session_id
