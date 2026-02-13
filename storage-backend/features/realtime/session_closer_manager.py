from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.providers.realtime.base import BaseRealtimeProvider

from .finalise import SessionTracker
from .metrics import RealtimeMetricsCollector
from .session_closer_state import (
    attach_provider as _attach_provider,
    cancel_timeout as _cancel_timeout,
    duration_seconds as _duration_seconds,
    prepare_session as _prepare_session,
    signal_close as _signal_close,
)
from .session_closer_cleanup import ensure_closed as _ensure_closed
from .session_closer_requests import (
    close_if_pending as _close_if_pending,
    request_close as _request_close,
    schedule_pending_close as _schedule_pending_close,
)


if TYPE_CHECKING:
    from asyncio import Event, Task
    from fastapi import WebSocket


class SessionClosureManager:
    """Coordinate websocket closure semantics for realtime sessions."""

    def __init__(self) -> None:
        self.websocket: "WebSocket" | None = None
        self.session_id: str = ""
        self.session_tracker: SessionTracker | None = None
        self.settings = None
        self.turn_state = None
        self.turn_context = None
        self.metrics: RealtimeMetricsCollector | None = None
        self.provider: BaseRealtimeProvider | None = None
        self.receiver_task: "Task" | None = None
        self.cancel_event: "Event" | None = None
        self.close_pending = False
        self.closure_timeout_task: "Task" | None = None
        self.session_closed = False
        self.session_start = asyncio.get_event_loop().time()
        self._close_requested = False
        self._close_reason: str | None = None
        self._pending_close_reason: str | None = None
        self._close_signal_sent = False

    def prepare(
        self,
        *,
        websocket: "WebSocket",
        session_id: str,
        tracker: SessionTracker,
        settings,
        turn_state,
        turn_context,
    ) -> None:
        _prepare_session(
            self,
            websocket=websocket,
            session_id=session_id,
            tracker=tracker,
            settings=settings,
            turn_state=turn_state,
            turn_context=turn_context,
        )

    def attach_provider(
        self,
        *,
        provider: BaseRealtimeProvider,
        receiver_task: "Task",
        cancel_event: asyncio.Event,
        metrics: RealtimeMetricsCollector,
    ) -> None:
        _attach_provider(
            self,
            provider=provider,
            receiver_task=receiver_task,
            cancel_event=cancel_event,
            metrics=metrics,
        )

    async def request_close(
        self, *, force: bool, reason: str | None = None
    ) -> bool:
        return await _request_close(self, force=force, reason=reason)

    async def close_if_pending(self) -> bool:
        return await _close_if_pending(self)

    async def ensure_closed(self) -> None:
        await _ensure_closed(self)

    def is_closed(self) -> bool:
        return self.session_closed

    def _cancel_timeout(self) -> None:
        _cancel_timeout(self)

    def _schedule_pending_close(self, reason: str | None) -> None:
        _schedule_pending_close(self, reason)

    def _signal_close(self, reason: str | None) -> None:
        _signal_close(self, reason)

    def _duration_seconds(self) -> float:
        return _duration_seconds(self)


__all__ = ["SessionClosureManager"]
