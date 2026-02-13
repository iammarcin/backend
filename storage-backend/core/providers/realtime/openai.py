"""OpenAI realtime provider integration.

This module exposes :class:`OpenAIRealtimeProvider`, a thin orchestrator around
websocket connectivity with the OpenAI Realtime API.  The provider is
responsible for establishing the session, handling lifecycle concerns and
delegating business logic to dedicated helper components.  Session
configuration parsing lives in :mod:`utils.openai_session`, while event
translation is encapsulated inside :mod:`utils.openai_events`, and audio
handling is managed by :mod:`audio_handler`.  Splitting responsibilities
keeps the file focused on the high-level workflow and makes future extensions
easier to reason about.
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from typing import Any, AsyncIterator, Awaitable, Callable, Mapping

from websockets.asyncio.client import ClientConnection, connect as ws_connect
from websockets.exceptions import ConnectionClosed, ConnectionClosedError, ConnectionClosedOK

from config.realtime.providers import openai as openai_config
from config.api_keys import OPENAI_API_KEY
from core.exceptions import ConfigurationError, ProviderError

from .audio_handler import AudioQueueHandler
from .base import BaseRealtimeProvider, RealtimeEvent
from .utils.openai_events import OpenAIRealtimeEventTranslator
from .utils.openai_session import SessionConfig

logger = logging.getLogger(__name__)


class OpenAIRealtimeProvider(BaseRealtimeProvider):
    """Realtime provider backed by the OpenAI Realtime API."""

    name = "openai-realtime"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        connect: Callable[..., Awaitable[ClientConnection | object]] | None = None,
    ) -> None:
        self._api_key = api_key or OPENAI_API_KEY
        self._connect = connect or ws_connect
        self._client: ClientConnection | None = None
        self._session_config: SessionConfig | None = None
        self._translator = OpenAIRealtimeEventTranslator()
        self._closed = False
        self._audio_handler = AudioQueueHandler()

    async def open_session(self, *, settings: Mapping[str, object]) -> None:
        """Establish a websocket connection to the OpenAI Realtime endpoint."""

        if not self._api_key:
            raise ConfigurationError(
                "OPENAI_API_KEY must be configured before using the realtime provider",
                key="OPENAI_API_KEY",
            )

        self._session_config = SessionConfig.from_settings(
            settings, default_model=openai_config.DEFAULT_MODEL
        )

        url = self._session_config.websocket_url
        headers = {
            "Authorization": f"Bearer {self._api_key}",
        }

        logger.info(
            "Connecting to OpenAI realtime endpoint",
            extra={"url": url, "model": self._session_config.model},
        )

        connect_kwargs = {"additional_headers": headers, "ping_interval": None}
        client = await self._connect(url, **connect_kwargs)
        if isinstance(client, asyncio.Future):  # pragma: no cover - defensive for custom connectors
            client = await client
        if not isinstance(client, ClientConnection):
            # Some tests provide lightweight stubs – rely on duck typing in that case
            self._client = client  # type: ignore[assignment]
        else:
            self._client = client

        await self._send_json(self._session_config.to_session_update_event())

        self._audio_handler.set_client(self._client)
        self._audio_handler.set_session_config(self._session_config)
        self._audio_handler.start_audio_sender()

    async def close_session(self) -> None:
        await self._audio_handler.stop_audio_sender()

        if self._client and not self._closed:
            try:
                await self._client.close()
            finally:
                self._closed = True
                self._client = None

    async def send_user_event(self, payload: Mapping[str, object]) -> None:
        if not self._client:
            raise ProviderError("OpenAI realtime session has not been initialised")

        if "binary" in payload:
            data = payload["binary"]
            if isinstance(data, (bytes, bytearray)):
                await self._client.send(data)
                return
            raise ProviderError("binary payload must be bytes-like")

        await self._send_json(payload)

    async def create_conversation_item(
        self,
        *,
        text: str | None = None,
        role: str = "user",
    ) -> None:
        """Send a ``conversation.item.create`` event to OpenAI.

        Uses the correct content type based on the role:
        - ``user`` messages use ``input_text``
        - ``assistant`` messages use ``text``
        """

        if not self._client:
            raise ProviderError("OpenAI realtime session has not been initialised")

        if not text:
            logger.warning("No text provided for realtime conversation item")
            return

        text_value = str(text)
        if not text_value.strip():
            logger.warning("Realtime conversation item text is empty after coercion")
            return

        content_type = "input_text" if role == "user" else "output_text"

        event = {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": role,
                "content": [{"type": content_type, "text": text_value}],
            },
        }

        await self._send_json(event)
        logger.debug(
            "Sending conversation item to OpenAI (role=%s, content_type=%s, chars=%d)",
            role,
            content_type,
            len(text_value),
        )

    async def request_response(self) -> None:
        """Request a response from the OpenAI realtime session."""

        if not self._client:
            raise ProviderError("OpenAI realtime session has not been initialised")

        await self._send_json(self._audio_handler.build_response_create_event())
        logger.debug("Sent response.create event to OpenAI realtime")

    async def receive_events(self) -> AsyncIterator[RealtimeEvent]:
        if not self._client:
            raise ProviderError("OpenAI realtime session has not been initialised")

        while True:
            try:
                message = await self._client.recv()
            except (ConnectionClosedOK, ConnectionClosedError, ConnectionClosed):
                logger.info("OpenAI realtime websocket closed")
                break

            if message is None:
                continue

            try:
                if isinstance(message, (bytes, bytearray)):
                    decoded = message.decode("utf-8")
                else:
                    decoded = str(message)
                event = json.loads(decoded)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Failed to parse realtime payload: %s", exc)
                continue

            for translated in self._translator.translate(event):
                yield translated

    async def cancel_turn(self) -> None:
        response_id = self._translator.current_response_id
        if not self._client or not response_id:
            return
        cancel_event = {
            "type": "response.cancel",
            "response_id": response_id,
        }
        await self._send_json(cancel_event)

    async def _send_json(self, payload: Mapping[str, object]) -> None:
        if not self._client:
            raise ProviderError("OpenAI realtime session has not been initialised")
        message = json.dumps(payload)
        await self._client.send(message)

    async def set_input_audio_queue(self, queue: asyncio.Queue[bytes | None]) -> None:
        await self._audio_handler.set_input_audio_queue(queue)

    async def _drain_audio_queue(self) -> None:  # pragma: no cover - exercised via tests
        await self._audio_handler._drain_audio_queue()


__all__ = ["OpenAIRealtimeProvider"]
