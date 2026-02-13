"""Handlers for editing chat history messages."""

from __future__ import annotations

from core.exceptions import DatabaseError

from features.chat.schemas.requests import EditMessageRequest
from features.chat.schemas.responses import (
    ChatSessionPayload,
    MessageWritePayload,
    MessageWriteResult,
)

from .base import HistoryRepositories, load_session_payload, resolve_ai_character
from .semantic_indexing import queue_semantic_indexing_tasks


async def edit_message(
    repositories: HistoryRepositories, request: EditMessageRequest
) -> MessageWritePayload:
    """Edit a previously stored message, creating the session if required."""

    if request.session_id:
        session_obj = await repositories.sessions.get_by_id(
            request.session_id,
            customer_id=request.customer_id,
            include_messages=False,
        )
    else:
        session_obj = None

    if session_obj is None:
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
    user_message_id: int | None = None
    user_message_obj = None
    user_index_action: str | None = None
    if request.user_message:
        payload = request.user_message.to_payload()
        if request.user_message.message_id:
            try:
                message = await repositories.messages.update_message(
                    message_id=request.user_message.message_id,
                    customer_id=request.customer_id,
                    payload=payload,
                )
                user_message_id = message.message_id
                user_message_obj = message
                user_index_action = "update"
            except DatabaseError:
                inserted = await repositories.messages.insert_message(
                    session_id=session_id,
                    customer_id=request.customer_id,
                    payload=payload,
                    is_ai_message=False,
                    claude_code_data=request.claude_code_data,
                )
                user_message_id = inserted.message_id
                user_message_obj = inserted
                user_index_action = "index"
        else:
            inserted = await repositories.messages.insert_message(
                session_id=session_id,
                customer_id=request.customer_id,
                payload=payload,
                is_ai_message=False,
                claude_code_data=request.claude_code_data,
            )
            user_message_id = inserted.message_id
            user_message_obj = inserted
            user_index_action = "index"

    ai_message_id: int | None = None
    ai_message_obj = None
    ai_index_action: str | None = None
    if request.ai_response and request.ai_response.has_content():
        payload = request.ai_response.to_payload()
        if request.ai_response.message_id:
            try:
                message = await repositories.messages.update_message(
                    message_id=request.ai_response.message_id,
                    customer_id=request.customer_id,
                    payload=payload,
                )
                ai_message_id = message.message_id
                ai_message_obj = message
                ai_index_action = "update"
            except DatabaseError:
                inserted = await repositories.messages.insert_message(
                    session_id=session_id,
                    customer_id=request.customer_id,
                    payload=payload,
                    is_ai_message=True,
                    claude_code_data=request.claude_code_data,
                )
                ai_message_id = inserted.message_id
                ai_message_obj = inserted
                ai_index_action = "index"
        else:
            inserted = await repositories.messages.insert_message(
                session_id=session_id,
                customer_id=request.customer_id,
                payload=payload,
                is_ai_message=True,
                claude_code_data=request.claude_code_data,
            )
            ai_message_id = inserted.message_id
            ai_message_obj = inserted
            ai_index_action = "index"

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
            (user_index_action, user_message_obj),
            (ai_index_action, ai_message_obj),
        ],
        session_obj=session_obj,
        customer_id=request.customer_id,
    )

    session_payload: ChatSessionPayload | None = None
    if request.session_id:
        session_payload = await load_session_payload(
            repositories,
            session_id,
            customer_id=request.customer_id,
            include_messages=True,
        )

    return MessageWritePayload(
        messages=MessageWriteResult(
            user_message_id=user_message_id or 0,
            ai_message_id=ai_message_id,
            session_id=session_id,
        ),
        session=session_payload,
    )


__all__ = ["edit_message"]
