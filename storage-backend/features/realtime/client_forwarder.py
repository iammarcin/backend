from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from typing import Awaitable, Callable, Mapping

from fastapi import WebSocket
from fastapi.websockets import WebSocketDisconnect

from core.providers.realtime.base import BaseRealtimeProvider

from .client_audio import handle_audio_payload
from .client_initial import dispatch_initial_payload
from .client_text import handle_text_payload
from .metrics import RealtimeMetricsCollector
from .state import RealtimeTurnState


logger = logging.getLogger(__name__)


class RealtimeClientForwarder:
    def __init__(
        self,
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
        self.websocket = websocket
        self.provider = provider
        self.session_id = session_id
        self.turn_state = turn_state
        self.parse_payload = parse_payload
        self.input_audio_queue = input_audio_queue
        self.cancel_event = cancel_event
        self.initial_payload = initial_payload
        self.metrics = metrics
        self.request_session_close = request_session_close

    async def forward(self) -> None:
        with suppress(WebSocketDisconnect):
            await dispatch_initial_payload(self)
            await self._receive_loop()

    async def _receive_loop(self) -> None:
        receive = getattr(self.websocket, "receive", None)
        receive_text = getattr(self.websocket, "receive_text", None)
        receive_bytes = getattr(self.websocket, "receive_bytes", None)

        while True:
            message = await self._receive_frame(receive, receive_text, receive_bytes)
            if message.get("type") == "websocket.disconnect":
                logger.info(
                    "Realtime websocket disconnect received (session=%s)",
                    self.session_id,
                )
                break

            processed_text = False
            text_data = message.get("text")
            if text_data is not None:
                processed_text = True
                should_close = await handle_text_payload(self, str(text_data))
                if should_close:
                    break

            audio_data = message.get("bytes")
            if audio_data is not None:
                await handle_audio_payload(self, audio_data)
                continue

            if processed_text:
                continue

            logger.debug(
                "Realtime websocket received unsupported frame (session=%s, keys=%s)",
                self.session_id,
                list(message.keys()),
            )

    async def _receive_frame(self, receive, receive_text, receive_bytes) -> dict[str, object]:
        if callable(receive):
            return await receive()

        message: dict[str, object] = {"type": "websocket.receive"}
        if callable(receive_text):
            message["text"] = await receive_text()
        elif callable(receive_bytes):
            message["bytes"] = await receive_bytes()
        else:  # pragma: no cover - defensive
            raise AttributeError("WebSocket stub must provide receive or receive_text")
        return message

    async def send_ack(self) -> None:
        await self.websocket.send_json(
            {
                "type": "realtime.ack",
                "session_id": self.session_id,
                "turn_status": self.turn_state.phase.value,
            }
        )


__all__ = ["RealtimeClientForwarder"]
