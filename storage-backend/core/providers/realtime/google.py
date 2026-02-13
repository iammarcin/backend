"""Google Gemini Live realtime provider implementation.

The module wires together websocket session management with
``GoogleSessionConfig`` and ``GoogleEventTranslator`` helpers so the main
provider stays focused on transport concerns.
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from typing import AsyncIterator, Awaitable, Callable, Mapping

from websockets.asyncio.client import ClientConnection, connect as ws_connect
from websockets.exceptions import ConnectionClosed, ConnectionClosedError, ConnectionClosedOK

from config.realtime.providers import google as google_config
from config.api_keys import GOOGLE_API_KEY
from core.exceptions import ConfigurationError, ProviderError

from .base import BaseRealtimeProvider, RealtimeEvent
from .utils.google_events import GoogleEventTranslator
from .utils.google_session import GoogleSessionConfig

logger = logging.getLogger(__name__)


class GoogleRealtimeProvider(BaseRealtimeProvider):
    """Realtime provider backed by Google Gemini Live."""

    name = "google-gemini-live"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        connect: Callable[..., Awaitable[ClientConnection | object]] | None = None,
    ) -> None:
        self._api_key = api_key or GOOGLE_API_KEY
        self._connect = connect or ws_connect
        self._client: ClientConnection | None = None
        self._session_config: GoogleSessionConfig | None = None
        self._translator = GoogleEventTranslator()
        self._closed = False
        self._input_audio_queue: asyncio.Queue[bytes | None] | None = None
        self._audio_sender_task: asyncio.Task[None] | None = None

    async def open_session(self, *, settings: Mapping[str, object]) -> None:
        """Establish a websocket session with Gemini Live."""

        if not self._api_key:
            raise ConfigurationError(
                "GOOGLE_API_KEY must be configured before using the realtime provider",
                key="GOOGLE_API_KEY",
            )

        model = str(settings.get("model") or google_config.DEFAULT_MODEL)
        voice = settings.get("voice") or google_config.DEFAULT_VOICE
        temperature = float(settings.get("temperature") or google_config.DEFAULT_TEMPERATURE)
        enable_audio_input = bool(settings.get("enable_audio_input", True))
        enable_audio_output = bool(settings.get("enable_audio_output", True))
        tts_auto_execute = bool(settings.get("tts_auto_execute", False))
        live_translation = bool(settings.get("live_translation", False))
        translation_language = settings.get("translation_language")

        self._session_config = GoogleSessionConfig(
            model=model,
            voice=str(voice) if voice else None,
            temperature=temperature,
            enable_audio_input=enable_audio_input,
            enable_audio_output=enable_audio_output,
            tts_auto_execute=tts_auto_execute,
            live_translation=live_translation,
            translation_language=str(translation_language) if translation_language else None,
        )
        self._translator.reset_response()

        url = (
            "wss://generativelanguage.googleapis.com/ws/"
            "google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent"
            f"?key={self._api_key}"
        )

        logger.info("Connecting to Gemini Live endpoint", extra={"url": url, "model": model})

        client = await self._connect(url, ping_interval=None)
        if isinstance(client, asyncio.Future):  # pragma: no cover
            client = await client
        if not isinstance(client, ClientConnection):
            self._client = client  # type: ignore[assignment]
        else:
            self._client = client

        await self._send_json(self._session_config.to_setup_event())

        if self._input_audio_queue and self._audio_sender_task is None:
            self._audio_sender_task = asyncio.create_task(self._drain_audio_queue())

    async def close_session(self) -> None:
        if self._audio_sender_task and not self._audio_sender_task.done():
            self._audio_sender_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._audio_sender_task
        self._audio_sender_task = None

        if self._client and not self._closed:
            try:
                await self._client.close()
            finally:
                self._closed = True
                self._client = None

    async def send_user_event(self, payload: Mapping[str, object]) -> None:
        if not self._client:
            raise ProviderError("Google realtime session has not been initialised")

        if "binary" in payload:
            data = payload["binary"]
            if isinstance(data, (bytes, bytearray)):
                await self._client.send(data)
                return
            raise ProviderError("binary payload must be bytes-like")

        await self._send_json(payload)

    async def receive_events(self) -> AsyncIterator[RealtimeEvent]:
        if not self._client:
            raise ProviderError("Google realtime session has not been initialised")

        while True:
            try:
                message = await self._client.recv()
            except (ConnectionClosedOK, ConnectionClosedError, ConnectionClosed):
                logger.info("Google realtime websocket closed")
                break

            if message is None:
                continue

            try:
                decoded = message.decode("utf-8") if isinstance(message, (bytes, bytearray)) else str(message)
                event = json.loads(decoded)
            except Exception as exc:  # pragma: no cover
                logger.warning("Failed to parse Gemini realtime payload: %s", exc)
                continue

            for translated in self._translator.translate(event):
                yield translated

    async def _send_json(self, payload: Mapping[str, object]) -> None:
        if not self._client:
            raise ProviderError("Google realtime session has not been initialised")
        message = json.dumps(payload)
        await self._client.send(message)

    async def set_input_audio_queue(self, queue: asyncio.Queue[bytes | None]) -> None:
        self._input_audio_queue = queue
        if self._audio_sender_task and not self._audio_sender_task.done():
            self._audio_sender_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._audio_sender_task
            self._audio_sender_task = None

    async def _drain_audio_queue(self) -> None:
        if not self._input_audio_queue or not self._client:
            return
        try:
            while True:
                chunk = await self._input_audio_queue.get()
                if chunk is None:
                    logger.info("Google realtime audio stream finished")
                    break
                if not chunk:
                    continue
                await self._client.send(chunk)
                logger.debug("Forwarded %s audio bytes to Google realtime", len(chunk))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Error forwarding audio to Google realtime: %s", exc, exc_info=True)


__all__ = ["GoogleRealtimeProvider"]
