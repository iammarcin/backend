from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from .session_closer_state import cancel_timeout, signal_close
from .state import TurnPhase


if TYPE_CHECKING:
    from .session_closer_manager import SessionClosureManager


logger = logging.getLogger(__name__)

_COMPLETION_STATUSES = {TurnPhase.COMPLETED, TurnPhase.CANCELLED, TurnPhase.ERRORED}


async def request_close(
    manager: "SessionClosureManager", *, force: bool, reason: str | None = None
) -> bool:
    if manager.session_closed:
        return True

    manager._close_requested = True
    if reason:
        manager._close_reason = reason

    status = getattr(manager.turn_state, "phase", None)
    vad_enabled = getattr(manager.settings, "vad_enabled", True)

    if force:
        from .session_closer_cleanup import ensure_closed

        await ensure_closed(manager)
        return True

    if (
        not vad_enabled
        and reason == "recording_finished"
        and status == TurnPhase.IDLE
    ):
        logger.info(
            "Single-turn mode: recording finished, waiting for provider response (session=%s)",
            manager.session_id,
        )
        schedule_pending_close(manager, reason)
        return False

    if reason == "turn_completed" and not vad_enabled:
        logger.info(
            "Single-turn mode: turn completed, closure will trigger on next event",
            extra={"session_id": manager.session_id},
        )
        signal_reason = reason or manager._pending_close_reason or manager._close_reason
        signal_close(manager, signal_reason)
        return True

    if status in _COMPLETION_STATUSES:
        signal_reason = reason or manager._pending_close_reason or manager._close_reason
        signal_close(manager, signal_reason)
        return True

    schedule_pending_close(manager, reason)
    return False


async def close_if_pending(manager: "SessionClosureManager") -> bool:
    if manager.session_closed or manager._close_signal_sent:
        return True

    if not manager.close_pending:
        return False

    status = getattr(manager.turn_state, "phase", None)
    status_value = getattr(status, "value", status) or "unknown"
    if status not in _COMPLETION_STATUSES:
        return False

    if (
        manager._pending_close_reason == "recording_finished"
        and not getattr(manager.settings, "vad_enabled", True)
        and status == TurnPhase.IDLE
    ):
        return False

    if status == TurnPhase.ERRORED:
        error_requires_close = getattr(manager.turn_state, "error_requires_close", True)
        error_severity = getattr(manager.turn_state, "error_severity", None)
        if not error_requires_close or (
            error_severity is not None and error_severity != "fatal"
        ):
            logger.info(
                "Closure pending but non-fatal error detected (severity=%s, session=%s)",
                error_severity or "unknown",
                manager.session_id,
            )
            return False

    logger.info(
        "Closure pending and turn is %s, signaling to close (session=%s)",
        str(status_value).upper(),
        manager.session_id,
    )
    signal_close(manager, manager._pending_close_reason)
    return True


def schedule_pending_close(manager: "SessionClosureManager", reason: str | None) -> None:
    if not manager.close_pending:
        manager.close_pending = True
    manager._pending_close_reason = reason
    cancel_timeout(manager)
    manager.closure_timeout_task = asyncio.create_task(wait_for_turn_completion(manager))


async def wait_for_turn_completion(manager: "SessionClosureManager") -> None:
    timeout = 10.0
    start = asyncio.get_event_loop().time()
    pending_reason = manager._pending_close_reason
    try:
        while not manager.session_closed:
            status = getattr(manager.turn_state, "phase", None)
            if status in _COMPLETION_STATUSES:
                if (
                    pending_reason == "recording_finished"
                    and not getattr(manager.settings, "vad_enabled", True)
                    and status == TurnPhase.IDLE
                ):
                    await asyncio.sleep(0.1)
                    continue
                break
            if asyncio.get_event_loop().time() - start >= timeout:
                break
            await asyncio.sleep(0.1)
    except asyncio.CancelledError:  # pragma: no cover - cancellation expected
        return
    from .session_closer_cleanup import ensure_closed

    await ensure_closed(manager)


__all__ = [
    "close_if_pending",
    "request_close",
    "schedule_pending_close",
    "wait_for_turn_completion",
]
