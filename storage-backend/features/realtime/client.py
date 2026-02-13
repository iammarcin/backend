"""Facade for client message forwarding helpers."""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Mapping

from fastapi import WebSocket

from core.providers.realtime.base import BaseRealtimeProvider

from .client_forwarder import RealtimeClientForwarder
from .metrics import RealtimeMetricsCollector
from .state import RealtimeTurnState


async def forward_client_messages(
    *,
    websocket: WebSocket,
    provider: BaseRealtimeProvider,
    session_id: str,
    turn_state: RealtimeTurnState,
    parse_payload: Callable[[str], Mapping[str, object] | None],
    input_audio_queue: asyncio.Queue[bytes | None],
    cancel_event: asyncio.Event,
    initial_payload: Mapping[str, object] | None = None,
    metrics: RealtimeMetricsCollector | None = None,
    request_session_close: Callable[[bool, str | None], Awaitable[bool] | bool]
    | Callable[[bool], Awaitable[bool] | bool]
    | None = None,
) -> None:
    forwarder = RealtimeClientForwarder(
        websocket=websocket,
        provider=provider,
        session_id=session_id,
        turn_state=turn_state,
        parse_payload=parse_payload,
        input_audio_queue=input_audio_queue,
        cancel_event=cancel_event,
        initial_payload=initial_payload,
        metrics=metrics,
        request_session_close=request_session_close,
    )
    await forwarder.forward()


__all__ = ["forward_client_messages"]
