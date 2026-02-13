from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from .event_factory import RealtimeEventFactory
from .provider_session import shutdown_provider_session
from .session_closer_state import cancel_timeout, duration_seconds


if TYPE_CHECKING:
    from .session_closer_manager import SessionClosureManager


logger = logging.getLogger(__name__)


async def ensure_closed(manager: "SessionClosureManager") -> None:
    if manager.session_closed:
        logger.debug(
            "Session already closed, skipping cleanup (session=%s)",
            manager.session_id,
        )
        return

    logger.info(
        "Ensuring session closure (session=%s, current_phase=%s)",
        manager.session_id,
        getattr(manager.turn_state, "phase", "unknown"),
        extra={
            "session_id": manager.session_id,
            "close_pending": manager.close_pending,
            "close_requested": manager._close_requested,
        },
    )

    manager.session_closed = True
    manager.close_pending = False
    cancel_timeout(manager)
    manager._pending_close_reason = None
    manager._close_signal_sent = False

    if manager.cancel_event and not manager.cancel_event.is_set():
        logger.debug(
            "Setting cancel event (session=%s)",
            manager.session_id,
        )
        manager.cancel_event.set()

    tracked_session_id = (
        manager.session_tracker.get_session_id() if manager.session_tracker else None
    )
    factory = RealtimeEventFactory(
        session_id=tracked_session_id or manager.session_id or "unknown"
    )
    payload = factory.session_closed(
        total_turns=getattr(manager.turn_context, "turn_number", 0),
        total_duration_ms=int(duration_seconds(manager) * 1000),
    ).model_dump(by_alias=True)

    if manager.websocket is not None:
        try:
            logger.debug(
                "Sending session.closed event to client (session=%s, turns=%d)",
                manager.session_id,
                getattr(manager.turn_context, "turn_number", 0),
            )
            await manager.websocket.send_json(payload)
        except Exception:  # pragma: no cover - best effort logging
            logger.debug(
                "Failed to send session.closed event (session=%s)",
                manager.session_id,
                exc_info=True,
            )

    logger.info(
        "Starting provider shutdown (session=%s)",
        manager.session_id,
        extra={"session_id": manager.session_id},
    )
    shutdown_start = time.time()
    try:
        await shutdown_provider(manager)
    except Exception as shutdown_exc:  # pragma: no cover - defensive logging
        shutdown_duration_ms = (time.time() - shutdown_start) * 1000
        logger.error(
            "Provider shutdown failed after %.2fms (session=%s): %s",
            shutdown_duration_ms,
            manager.session_id,
            shutdown_exc,
            extra={
                "session_id": manager.session_id,
                "shutdown_duration_ms": shutdown_duration_ms,
                "exception_type": type(shutdown_exc).__name__,
            },
            exc_info=True,
        )
    else:
        shutdown_duration_ms = (time.time() - shutdown_start) * 1000
        logger.info(
            "Provider shutdown completed in %.2fms (session=%s)",
            shutdown_duration_ms,
            manager.session_id,
            extra={
                "session_id": manager.session_id,
                "shutdown_duration_ms": shutdown_duration_ms,
            },
        )

    if manager.websocket is not None:
        try:
            logger.debug(
                "Closing websocket connection (session=%s)",
                manager.session_id,
            )
            await manager.websocket.close(code=1000, reason="session_closed")
            logger.debug(
                "Websocket connection closed (session=%s)",
                manager.session_id,
            )
        except Exception:  # pragma: no cover - best effort logging
            logger.debug(
                "Failed to close realtime websocket (session=%s)",
                manager.session_id,
                exc_info=True,
            )

    if manager.session_tracker:
        logger.debug(
            "Clearing session tracker (session=%s)",
            manager.session_id,
        )
        manager.session_tracker.set_session_id(None)

    total_duration_seconds = duration_seconds(manager)
    total_turns = getattr(manager.turn_context, "turn_number", 0)
    logger.info(
        "Session closure complete (session=%s, duration=%.2fs, turns=%d)",
        manager.session_id,
        total_duration_seconds,
        total_turns,
        extra={
            "session_id": manager.session_id,
            "total_duration_seconds": total_duration_seconds,
            "total_turns": total_turns,
        },
    )


async def shutdown_provider(manager: "SessionClosureManager") -> None:
    provider = manager.provider
    task = manager.receiver_task
    if provider and task:
        logger.debug(
            "Shutting down provider session (provider=%s, task_done=%s, session=%s)",
            getattr(provider, "name", "unknown"),
            task.done(),
            manager.session_id,
        )
        shutdown_start = time.time()
        try:
            await shutdown_provider_session(
                provider=provider,
                receiver_task=task,
                metrics=manager.metrics,
            )
        except Exception as shutdown_exc:  # pragma: no cover - defensive logging
            shutdown_duration_ms = (time.time() - shutdown_start) * 1000
            logger.warning(
                "Provider session shutdown raised exception after %.2fms (session=%s): %s",
                shutdown_duration_ms,
                manager.session_id,
                shutdown_exc,
                exc_info=True,
            )
        else:
            shutdown_duration_ms = (time.time() - shutdown_start) * 1000
            logger.debug(
                "Provider session shutdown completed in %.2fms (session=%s)",
                shutdown_duration_ms,
                manager.session_id,
            )
    elif task and not task.done():
        logger.debug(
            "Cancelling receiver task without provider (task_done=%s, session=%s)",
            task.done(),
            manager.session_id,
        )
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            logger.debug(
                "Receiver task cancelled successfully (session=%s)",
                manager.session_id,
            )
        except Exception as task_exc:  # pragma: no cover - defensive cleanup
            logger.warning(
                "Receiver task raised exception during cancellation (session=%s): %s",
                manager.session_id,
                task_exc,
                exc_info=True,
            )
    else:
        logger.debug(
            "No provider or task to shutdown (provider=%s, task=%s, session=%s)",
            provider is not None,
            task is not None,
            manager.session_id,
        )

    if manager.metrics:
        logger.debug(
            "Cleaning up metrics collector (session=%s)",
            manager.session_id,
        )
        try:
            manager.metrics.cleanup()
        except Exception as metrics_exc:  # pragma: no cover - defensive logging
            logger.warning(
                "Metrics cleanup failed (session=%s): %s",
                manager.session_id,
                metrics_exc,
                exc_info=True,
            )
    manager.provider = None
    manager.receiver_task = None
    manager.metrics = None
    logger.debug(
        "Provider shutdown cleanup complete (session=%s)",
        manager.session_id,
    )


__all__ = ["ensure_closed", "shutdown_provider"]
