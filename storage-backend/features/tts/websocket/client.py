"""Client for the ElevenLabs realtime websocket API."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import suppress
from typing import Any, Dict
from urllib.parse import urlencode

from config.tts.providers import elevenlabs as elevenlabs_config
from core.exceptions import ConfigurationError
from config.tts.utils import ElevenLabsRealtimeSettings

logger = logging.getLogger(__name__)


class ElevenLabsRealtimeClient:
    """Thin wrapper around the ElevenLabs realtime websocket API."""

    def __init__(self, settings: ElevenLabsRealtimeSettings) -> None:
        if not elevenlabs_config.API_KEY:
            raise ConfigurationError(
                "ELEVEN_API_KEY must be configured for realtime TTS", key="ELEVEN_API_KEY"
            )
        self._settings = settings

    async def run(
        self,
        text_queue: "asyncio.Queue[str | None]",
        audio_queue: "asyncio.Queue[dict[str, Any] | None]",
        timings: Dict[str, float],
        stop_event: asyncio.Event,
    ) -> None:
        """Stream audio from ElevenLabs based on text queue input."""

        import websockets

        query = {
            "model_id": self._settings.model,
            "inactivity_timeout": str(self._settings.inactivity_timeout),
            "output_format": self._settings.audio_format,
        }
        query_string = urlencode(query)
        uri = (
            "wss://api.elevenlabs.io/v1/text-to-speech/"
            f"{self._settings.voice}/stream-input?{query_string}"
        )

        async with websockets.connect(uri, ping_interval=None) as ws:  # type: ignore[call-arg]
            init_payload = {
                "text": " ",
                "voice_settings": {
                    "stability": self._settings.stability,
                    "similarity_boost": self._settings.similarity_boost,
                    "style": self._settings.style,
                    "use_speaker_boost": self._settings.speaker_boost,
                },
                "generation_config": {
                    "chunk_length_schedule": self._settings.chunk_schedule,
                },
                "xi_api_key": elevenlabs_config.API_KEY,
            }
            await ws.send(json.dumps(init_payload))
            timings["tts_request_sent_time"] = time.time()

            listener = asyncio.create_task(
                self._listen_for_audio(ws, audio_queue, timings, stop_event)
            )
            try:
                while True:
                    if stop_event.is_set():
                        await ws.send(json.dumps({"text": ""}))
                        break

                    text_chunk = await text_queue.get()
                    if text_chunk is None:
                        await ws.send(json.dumps({"text": ""}))
                        break
                    await ws.send(json.dumps({"text": text_chunk}))
            finally:
                with suppress(Exception):
                    await ws.send(json.dumps({"text": ""}))
                await listener
                timings["tts_completed_time"] = time.time()
                await audio_queue.put({"type": "status", "status": "finished"})
                await audio_queue.put(None)

    async def _listen_for_audio(
        self,
        ws: "websockets.WebSocketClientProtocol",
        audio_queue: "asyncio.Queue[dict[str, Any] | None]",
        timings: Dict[str, float],
        stop_event: asyncio.Event,
    ) -> None:
        """Consume ElevenLabs websocket messages and push them onto ``audio_queue``."""

        import websockets

        try:
            async for message in ws:
                if stop_event.is_set():
                    break
                data = json.loads(message)
                audio_data = data.get("audio")
                if audio_data:
                    if "tts_first_response_time" not in timings:
                        timings["tts_first_response_time"] = time.time()
                    await audio_queue.put({"type": "audio", "chunk": audio_data})
                status = data.get("status")
                if status:
                    await audio_queue.put({"type": "status", "status": status, "raw": data})
                if status == "finished":
                    break
        except websockets.exceptions.ConnectionClosedOK:
            logger.debug("ElevenLabs realtime websocket closed normally")
        except websockets.exceptions.ConnectionClosedError as exc:
            logger.warning("ElevenLabs realtime websocket closed with error: %s", exc)
            await audio_queue.put({"type": "error", "message": str(exc)})
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Unexpected error while listening for ElevenLabs audio")
            await audio_queue.put({"type": "error", "message": str(exc)})


__all__ = ["ElevenLabsRealtimeClient"]
