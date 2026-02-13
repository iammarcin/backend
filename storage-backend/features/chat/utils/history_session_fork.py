"""Support for the "New session from here" workflow in chat history."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import WebSocket
from pydantic import ValidationError as PydanticValidationError

from core.exceptions import ConfigurationError, DatabaseError, ValidationError
from core.streaming.manager import StreamingManager
from features.chat.service import ChatHistoryService
from infrastructure.db.mysql import require_main_session_factory, session_scope

from .websocket_session import WorkflowSession

logger = logging.getLogger(__name__)


async def handle_new_session_from_here(
    *,
    websocket: WebSocket,
    session: WorkflowSession,
    user_input: Dict[str, Any],
    chat_history: List[Any],
    customer_id: int,
    manager: StreamingManager,
) -> bool:
    """Create a forked chat session when requested by the client.

    Returns ``True`` if the session was successfully forked. On failure the
    function notifies the client and returns ``False``.
    """

    try:
        session_factory = require_main_session_factory()
    except ConfigurationError as exc:
        logger.error("Chat database not configured: %s", exc)
        await manager.send_event(
            {
                "type": "error",
                "stage": "database",
                "content": "Chat database not configured",
                "session_id": session.session_id,
            }
        )
        return False

    ai_character_name = user_input.get("new_ai_character_name", "assistant")
    ai_text_gen_model = user_input.get("ai_text_gen_model")
    claude_code_data = user_input.get("claudeCodeData")

    try:
        async with session_scope(session_factory) as db_session:
            service = ChatHistoryService(db_session)
            new_session_id = await service.fork_session_from_history(
                customer_id=customer_id,
                chat_history=chat_history,
                session_name="New session from here",
                ai_character_name=ai_character_name,
                ai_text_gen_model=ai_text_gen_model,
                claude_code_data=claude_code_data,
            )

        logger.info(
            "Forked new session %s with %d messages for customer %s",
            new_session_id,
            len(chat_history),
            customer_id,
        )

        user_input["session_id"] = new_session_id
        return True

    except (DatabaseError, ValidationError, PydanticValidationError) as exc:
        logger.error("Failed to fork session: %s", exc)
        await manager.send_event(
            {
                "type": "error",
                "stage": "database",
                "content": f"Failed to fork session: {str(exc)}",
                "session_id": session.session_id,
            }
        )
        return False
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Unexpected error forking session: %s", exc, exc_info=True)
        await manager.send_event(
            {
                "type": "error",
                "stage": "database",
                "content": "Unexpected error forking session",
                "session_id": session.session_id,
            }
        )
        return False


__all__ = ["handle_new_session_from_here"]
