from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from fastapi import WebSocket

    from core.providers.realtime.base import BaseRealtimeProvider

    from .finalise import SessionTracker
    from .metrics import RealtimeMetricsCollector
    from .session_closer_manager import SessionClosureManager


logger = logging.getLogger(__name__)


def prepare_session(
    manager: "SessionClosureManager",
    *,
    websocket: "WebSocket",
    session_id: str,
    tracker: "SessionTracker",
    settings,
    turn_state,
    turn_context,
) -> None:
    manager.websocket = websocket
    manager.session_id = session_id
    manager.session_tracker = tracker
    manager.settings = settings
    manager.turn_state = turn_state
    manager.turn_context = turn_context
    manager.session_closed = False
    manager.close_pending = False
    manager.session_start = asyncio.get_event_loop().time()
    cancel_timeout(manager)
    manager._close_requested = False
    manager._close_reason = None
    manager._pending_close_reason = None
    manager._close_signal_sent = False


def attach_provider(
    manager: "SessionClosureManager",
    *,
    provider: "BaseRealtimeProvider",
    receiver_task: asyncio.Task,
    cancel_event: asyncio.Event,
    metrics: "RealtimeMetricsCollector",
) -> None:
    manager.provider = provider
    manager.receiver_task = receiver_task
    manager.cancel_event = cancel_event
    manager.metrics = metrics


def cancel_timeout(manager: "SessionClosureManager") -> None:
    task = manager.closure_timeout_task
    if task and not task.done():
        task.cancel()
    manager.closure_timeout_task = None


def signal_close(manager: "SessionClosureManager", reason: str | None) -> None:
    if manager._close_signal_sent:
        return

    manager._close_signal_sent = True
    logger.info(
        "Closure pending, signaling to close session (session=%s)",
        manager.session_id,
    )
    if reason and not manager._pending_close_reason:
        manager._pending_close_reason = reason


def duration_seconds(manager: "SessionClosureManager") -> float:
    return asyncio.get_event_loop().time() - manager.session_start


__all__ = [
    "attach_provider",
    "cancel_timeout",
    "duration_seconds",
    "prepare_session",
    "signal_close",
]
