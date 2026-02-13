"""Core implementation for persisting streamed chat workflows."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from fastapi import WebSocket
from pydantic import ValidationError as PydanticValidationError

from core.exceptions import ConfigurationError, DatabaseError
from core.streaming.manager import StreamingManager
from features.chat.schemas.requests import CreateMessageRequest, EditMessageRequest
from infrastructure.db.mysql import require_main_session_factory

from .history_metadata import build_request_metadata
from .history_payloads import (
    build_ai_message_payload,
    build_user_message_payload,
    coerce_dict,
    resolve_prompt_text,
)
from .history_persistence_deep_research import (
    persist_complete_deep_research_workflow,
)
from .history_persistence_helpers import (
    ensure_baseline_timings,
    execute_history_call,
    extract_transcription,
)
from .history_session_fork import handle_new_session_from_here
from .history_tts_persistence import persist_tts_only_result
from .websocket_session import WorkflowSession
from .websocket_workflow_executor import StandardWorkflowOutcome

logger = logging.getLogger(__name__)


async def persist_workflow_result(
    *,
    websocket: WebSocket,
    session: WorkflowSession,
    request_data: Dict[str, Any],
    settings: Dict[str, Any],
    workflow: StandardWorkflowOutcome,
    customer_id: int,
    manager: StreamingManager,
) -> None:
    """Persist the streamed workflow result and notify the frontend."""

    request_type = request_data.get("request_type")
    if request_type == "tts":
        await persist_tts_only_result(
            websocket=websocket,
            session=session,
            request_data=request_data,
            settings=settings,
            workflow=workflow,
            customer_id=customer_id,
            manager=manager,
        )
        return

    user_input = coerce_dict(request_data.get("user_input"))
    if not user_input:
        logger.info("Skipping history persistence due to missing user_input payload")
        return

    if workflow.result.get("is_deep_research"):
        logger.info("Deep research workflow detected - using specialized persistence")
        await persist_complete_deep_research_workflow(
            websocket=websocket,
            session=session,
            customer_id=customer_id,
            user_input=user_input,
            settings=settings,
            workflow=workflow,
            manager=manager,
        )
        return

    chat_history = user_input.get("new_session_from_here_full_chat_history")
    if chat_history and isinstance(chat_history, list) and len(chat_history) > 0:
        logger.info(
            "Processing new session from here request with %d historical messages",
            len(chat_history),
        )
        forked = await handle_new_session_from_here(
            websocket=websocket,
            session=session,
            user_input=user_input,
            chat_history=chat_history,
            customer_id=customer_id,
            manager=manager,
        )
        if not forked:
            return

    prompt_payload = request_data.get("prompt")
    prompt = prompt_payload if prompt_payload is not None else workflow.prompt_for_preview
    prompt_text = resolve_prompt_text(prompt)

    timings = ensure_baseline_timings(workflow.timings)
    transcription = extract_transcription(workflow, request_data, user_input)

    try:
        user_message = build_user_message_payload(
            user_input=user_input,
            prompt_text=prompt_text,
            timings=timings,
            transcription=transcription,
        )
    except PydanticValidationError as exc:
        await _send_error(
            websocket,
            session=session,
            message="Invalid user message payload",
            manager=manager,
        )
        logger.error("Failed to prepare user message payload: %s", exc)
        return

    ai_message = build_ai_message_payload(
        user_input=user_input,
        settings=settings,
        workflow=workflow,
        timings=timings,
    )

    is_edit = bool(
        user_input.get("is_edited_message") or request_data.get("is_edited_message")
    )

    request_metadata = build_request_metadata(
        user_input=user_input,
        settings=settings,
        workflow=workflow,
        customer_id=customer_id,
    )

    try:
        if is_edit:
            request_model = EditMessageRequest(
                **request_metadata,
                user_message=user_message if user_message.has_content() else None,
                ai_response=ai_message,
            )
        else:
            request_model = CreateMessageRequest(
                **request_metadata,
                user_message=user_message,
                ai_response=ai_message,
            )
    except PydanticValidationError as exc:
        await _send_error(
            websocket,
            session=session,
            message="Invalid history payload",
            manager=manager,
        )
        logger.error("Failed to build history request payload: %s", exc)
        return

    try:
        session_factory = require_main_session_factory()
    except ConfigurationError as exc:
        await _send_error(
            websocket,
            session=session,
            message="Chat database not configured",
            manager=manager,
        )
        logger.error("Chat database not configured: %s", exc)
        return

    try:
        result_payload = await execute_history_call(
            session_factory=session_factory,
            request_model=request_model,
            is_edit=is_edit,
        )
    except (DatabaseError, PydanticValidationError) as exc:
        await _send_error(
            websocket,
            session=session,
            message="Failed to save chat history",
            manager=manager,
        )
        logger.error("Failed to persist chat history: %s", exc)
        return
    except Exception as exc:  # pragma: no cover - defensive logging
        await _send_error(
            websocket,
            session=session,
            message="Unexpected error while saving chat history",
            manager=manager,
        )
        logger.error("Unexpected error while saving chat history: %s", exc, exc_info=True)
        return

    logger.info(
        "Persisted chat workflow for customer %s (session_id=%s)",
        customer_id,
        result_payload.get("session_id"),
    )

    await manager.send_event(
        {
            "type": "db_operation_executed",
            "content": json.dumps(result_payload),
            "session_id": session.session_id,
        }
    )


async def _send_error(websocket: WebSocket, *, session: WorkflowSession, message: str, manager: StreamingManager) -> None:
    await manager.send_event(
        {
            "type": "error",
            "stage": "database",
            "content": message,
            "session_id": session.session_id,
        }
    )


__all__ = ["persist_workflow_result"]
