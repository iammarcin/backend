from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from fastapi import WebSocket

from core.exceptions import ServiceError

from .errors import persistence_failed_error

if TYPE_CHECKING:
    from .event_factory import RealtimeEventFactory
    from .turn_finaliser import TurnFinaliser


logger = logging.getLogger(__name__)


async def persist_chat_history(
    *,
    finaliser: "TurnFinaliser",
    request,
    websocket: WebSocket,
    session_id: str,
    turn_number: int,
    event_factory: "RealtimeEventFactory",
):
    start_time = time.time()
    logger.info(
        "Starting database write for turn %d (session=%s)",
        turn_number,
        session_id,
        extra={
            "session_id": session_id,
            "turn_number": turn_number,
            "user_message_length": len(request.user_message.message or ""),
            "assistant_message_length": len(request.ai_response.message or "") if request.ai_response else 0,
            "has_audio": bool(request.ai_response and request.ai_response.file_names),
        },
    )

    try:
        write_result = await finaliser.chat_history_service.create_message(request)
        _log_write_success(
            write_result=write_result,
            session_id=session_id,
            turn_number=turn_number,
            start_time=start_time,
        )
        await _commit_transaction(
            finaliser=finaliser,
            session_id=session_id,
            turn_number=turn_number,
        )
        return write_result
    except ServiceError as exc:
        await _handle_service_error(
            exc=exc,
            start_time=start_time,
            websocket=websocket,
            session_id=session_id,
            turn_number=turn_number,
            event_factory=event_factory,
        )
        return None


def update_session_tracker(
    *,
    finaliser: "TurnFinaliser",
    persisted_session_id: str | None,
    session_id: str,
    turn_number: int,
) -> None:
    if not persisted_session_id:
        logger.warning(
            "Database write returned no session_id for turn %d (session=%s)",
            turn_number,
            session_id,
            extra={
                "session_id": session_id,
                "turn_number": turn_number,
            },
        )
        return

    previous_session_id = finaliser.session_tracker.get_session_id()
    finaliser.session_tracker.set_session_id(persisted_session_id)
    if previous_session_id != persisted_session_id:
        logger.info(
            "Session tracker updated (websocket_session=%s, db_session=%s, turn=%d)",
            session_id,
            persisted_session_id,
            turn_number,
            extra={
                "websocket_session_id": session_id,
                "db_session_id": persisted_session_id,
                "previous_db_session_id": previous_session_id,
                "turn_number": turn_number,
            },
        )
    else:
        logger.debug(
            "Session tracker confirmed (db_session=%s, turn=%d)",
            persisted_session_id,
            turn_number,
        )


def _log_write_success(*, write_result, session_id: str, turn_number: int, start_time: float) -> None:
    duration_ms = (time.time() - start_time) * 1000
    logger.info(
        "Database write succeeded for turn %d in %.2fms (session=%s, "
        "user_msg_id=%s, ai_msg_id=%s, db_session_id=%s)",
        turn_number,
        duration_ms,
        session_id,
        write_result.messages.user_message_id,
        write_result.messages.ai_message_id,
        write_result.messages.session_id,
        extra={
            "session_id": session_id,
            "turn_number": turn_number,
            "duration_ms": duration_ms,
            "user_message_id": str(write_result.messages.user_message_id),
            "ai_message_id": str(write_result.messages.ai_message_id),
            "db_session_id": write_result.messages.session_id,
        },
    )


async def _commit_transaction(*, finaliser: "TurnFinaliser", session_id: str, turn_number: int) -> None:
    commit_start = time.time()
    db_session = getattr(finaliser.chat_history_service, "_session", None)
    if db_session is None:
        logger.warning(
            "No database session found to commit for turn %d (session=%s)",
            turn_number,
            session_id,
            extra={
                "session_id": session_id,
                "turn_number": turn_number,
            },
        )
        return

    try:
        await db_session.commit()
    except Exception as commit_exc:  # pragma: no cover - defensive logging
        commit_duration_ms = (time.time() - commit_start) * 1000
        logger.error(
            "Failed to commit database transaction for turn %d after %.2fms "
            "(session=%s, type=%s): %s",
            turn_number,
            commit_duration_ms,
            session_id,
            type(commit_exc).__name__,
            str(commit_exc),
            extra={
                "session_id": session_id,
                "turn_number": turn_number,
                "commit_duration_ms": commit_duration_ms,
                "exception_type": type(commit_exc).__name__,
            },
            exc_info=True,
        )
    else:
        commit_duration_ms = (time.time() - commit_start) * 1000
        logger.info(
            "Database transaction committed for turn %d in %.2fms (session=%s)",
            turn_number,
            commit_duration_ms,
            session_id,
            extra={
                "session_id": session_id,
                "turn_number": turn_number,
                "commit_duration_ms": commit_duration_ms,
            },
        )


async def _handle_service_error(
    *,
    exc: ServiceError,
    start_time: float,
    websocket: WebSocket,
    session_id: str,
    turn_number: int,
    event_factory: "RealtimeEventFactory",
) -> None:
    duration_ms = (time.time() - start_time) * 1000
    error = persistence_failed_error(str(exc))
    logger.error(
        "Database write failed with ServiceError for turn %d after %.2fms (session=%s): %s",
        turn_number,
        duration_ms,
        session_id,
        str(exc),
        extra={
            "session_id": session_id,
            "turn_number": turn_number,
            "duration_ms": duration_ms,
            "error_code": error.code.value,
            "error_message": str(exc),
        },
        exc_info=True,
    )
    error_event = event_factory.error_from_realtime_error(
        error,
        turn_number=turn_number,
    )
    await websocket.send_text(error_event.model_dump_json())


__all__ = ["persist_chat_history", "update_session_tracker"]
