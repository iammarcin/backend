"""Handlers for creating chat history messages."""

from __future__ import annotations

from core.exceptions import DatabaseError

from features.chat.schemas.requests import CreateMessageRequest
from features.chat.schemas.responses import (
    ChatSessionPayload,
    MessageWritePayload,
    MessageWriteResult,
)

from .base import HistoryRepositories, load_session_payload, resolve_ai_character
from .semantic_indexing import queue_semantic_indexing_tasks


async def create_message(
    repositories: HistoryRepositories, request: CreateMessageRequest
) -> MessageWritePayload:
    """Insert a new user message and optional AI response."""

    if request.session_id:
        session_obj = await repositories.sessions.get_by_id(
            request.session_id,
            customer_id=request.customer_id,
            include_messages=False,
        )
        if session_obj is None:
            raise DatabaseError(
                "Chat session not found", operation="create_message"
            )
    else:
        session_obj = await repositories.sessions.create_session(
            customer_id=request.customer_id,
            session_name=request.session_name or "New chat",
            ai_character_name=resolve_ai_character(
                request.ai_character_name, request.user_settings
            ),
            ai_text_gen_model=request.ai_text_gen_model,
            tags=request.tags,
            auto_trigger_tts=request.auto_trigger_tts,
            claude_session_id=request.claude_session_id,
        )

    session_id = session_obj.session_id
    user_message = await repositories.messages.insert_message(
        session_id=session_id,
        customer_id=request.customer_id,
        payload=request.user_message.to_payload(),
        is_ai_message=False,
        claude_code_data=request.claude_code_data,
    )

    ai_message_id: int | None = None
    ai_message_obj = None
    if request.ai_response and request.ai_response.has_content():
        ai_message = await repositories.messages.insert_message(
            session_id=session_id,
            customer_id=request.customer_id,
            payload=request.ai_response.to_payload(),
            is_ai_message=True,
            claude_code_data=request.claude_code_data,
        )
        ai_message_id = ai_message.message_id
        ai_message_obj = ai_message

    session_obj = await repositories.sessions.update_session_metadata(
        session_id=session_id,
        customer_id=request.customer_id,
        session_name=request.session_name,
        ai_character_name=request.ai_character_name,
        auto_trigger_tts=request.auto_trigger_tts,
        ai_text_gen_model=request.ai_text_gen_model,
        tags=request.tags,
        claude_session_id=request.claude_session_id,
        update_last_mod_time=request.update_last_mod_time,
    )

    await queue_semantic_indexing_tasks(
        entries=[
            ("index", user_message),
            ("index", ai_message_obj),
        ],
        session_obj=session_obj,
        customer_id=request.customer_id,
    )

    session_payload: ChatSessionPayload | None = None
    if request.include_messages:
        session_payload = await load_session_payload(
            repositories,
            session_id,
            customer_id=request.customer_id,
            include_messages=True,
        )

    return MessageWritePayload(
        messages=MessageWriteResult(
            user_message_id=user_message.message_id,
            ai_message_id=ai_message_id,
            session_id=session_id,
        ),
        session=session_payload,
    )


__all__ = ["create_message"]
