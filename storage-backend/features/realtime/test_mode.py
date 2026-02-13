"""Utilities for emitting deterministic realtime events during manual testing."""

from __future__ import annotations

import logging
from contextlib import suppress
from typing import Awaitable, Callable, Iterable, Mapping

from fastapi import WebSocket
from fastapi.websockets import WebSocketDisconnect

from core.observability import render_payload_preview
from core.providers.realtime.base import RealtimeEvent, RealtimeEventType
from features.realtime.schemas import RealtimeSessionSettings
from features.realtime.state import RealtimeTurnState

from .context import RealtimeTurnContext

logger = logging.getLogger(__name__)


async def run_test_mode(
    *,
    websocket: WebSocket,
    session_id: str,
    customer_id: int,
    turn_state: RealtimeTurnState,
    turn_context: RealtimeTurnContext,
    settings: RealtimeSessionSettings,
    parse_payload: Callable[[str], Mapping[str, object] | None],
    handle_event: Callable[[RealtimeEvent], Awaitable[bool]],
) -> None:
    """Emit canned events without involving external realtime providers."""

    with suppress(WebSocketDisconnect):
        raw_message = await websocket.receive_text()
        payload = parse_payload(raw_message)
        if payload is not None:
            logger.debug(
                "Realtime websocket test-mode payload (session=%s): %s",
                session_id,
                render_payload_preview(payload),
            )
        await websocket.send_json(
            {
                "type": "realtime.ack",
                "session_id": session_id,
                "turn_status": turn_state.phase.value,
            }
        )

    for event in build_test_mode_events():
        should_close = await handle_event(event)
        if should_close:
            close = getattr(websocket, "close", None)
            if callable(close):
                with suppress(Exception):  # pragma: no cover - defensive
                    await close(code=1000, reason="single_turn_complete")
            break


def build_test_mode_events() -> Iterable[RealtimeEvent]:
    """Return the synthetic events representing a single successful turn."""

    return [
        RealtimeEvent(
            RealtimeEventType.MESSAGE,
            {"event": "user.transcript.completed", "text": "Hello from test mode"},
        ),
        RealtimeEvent(
            RealtimeEventType.MESSAGE,
            {
                "event": "assistant.text.delta",
                "response_id": "test-response",
                "text": "This is a prerecorded response.",
            },
        ),
        RealtimeEvent(
            RealtimeEventType.MESSAGE,
            {
                "event": "assistant.text.completed",
                "response_id": "test-response",
            },
        ),
        RealtimeEvent(
            RealtimeEventType.CONTROL,
            {
                "event": "turn.completed",
                "response_id": "test-response",
                "status": "completed",
            },
        ),
    ]


__all__ = ["run_test_mode", "build_test_mode_events"]
