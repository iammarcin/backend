"""Deepgram websocket audio provider implementation."""

from __future__ import annotations

import asyncio
import logging
import urllib.parse
from contextlib import suppress
from typing import Any, AsyncIterator, Mapping

from websockets.asyncio.client import connect

try:
    from websockets.exceptions import ConnectionClosedError, InvalidStatus
except ImportError:  # pragma: no cover - backwards compatibility
    from websockets.exceptions import ConnectionClosed as ConnectionClosedError
    from websockets.exceptions import InvalidStatusCode as InvalidStatus

from config.audio.providers import deepgram as deepgram_config
from core.exceptions import ProviderError, ServiceError
from core.providers.audio.base import (
    BaseAudioProvider,
    SpeechProviderRequest,
    SpeechTranscriptionResult,
)
from features.audio.deepgram_helpers import (
    KeepAliveState,
    receive_transcription,
    send_audio_chunks,
    send_keepalive_messages,
)

logger = logging.getLogger(__name__)


class DeepgramSpeechProvider(BaseAudioProvider):
    """Provide Deepgram powered speech to text streaming."""

    name = "deepgram"
    streaming_capable = True

    def __init__(self) -> None:
        self.url = "wss://api.eu.deepgram.com/v1/listen"
        self.model = deepgram_config.DEFAULT_MODEL
        self.language = deepgram_config.DEFAULT_LANGUAGE
        self.encoding = "linear16"
        self.sample_rate = 16000
        self.recording_sample_rate = 24000
        self.channels = 1
        self.punctuate = True
        self.interim_results = False
        self.numerals = True
        self.profanity_filter = False

    def configure(self, settings: Mapping[str, Any]) -> None:  # type: ignore[override]
        """Apply Deepgram specific configuration parameters."""

        if not settings:
            return

        # Model is already normalized by settings.py before being passed here
        self.model = str(settings.get("model", self.model))
        self.language = str(settings.get("language", self.language))
        self.encoding = str(settings.get("encoding", self.encoding))
        self.sample_rate = int(settings.get("sample_rate", self.sample_rate))
        self.recording_sample_rate = int(
            settings.get("recording_sample_rate", self.recording_sample_rate)
        )
        self.channels = int(settings.get("channels", self.channels))
        self.punctuate = bool(settings.get("punctuate", self.punctuate))
        self.interim_results = bool(
            settings.get("interim_results", self.interim_results)
        )
        self.numerals = bool(settings.get("numerals", self.numerals))
        self.profanity_filter = bool(
            settings.get("profanity_filter", self.profanity_filter)
        )

        logger.info(
            "Configured Deepgram provider (model=%s, language=%s, sample_rate=%s, recording_rate=%s)",
            self.model,
            self.language,
            self.sample_rate,
            self.recording_sample_rate,
        )

    async def transcribe_file(
        self, request: SpeechProviderRequest
    ) -> SpeechTranscriptionResult:  # pragma: no cover - not part of milestone scope
        raise ProviderError(
            "Deepgram provider supports streaming transcription only",
            provider=self.name,
        )

    async def transcribe_stream(
        self,
        *,
        audio_source: AsyncIterator[bytes | None],
        manager,
        mode: str = "non-realtime",
    ) -> str:
        if not deepgram_config.API_KEY:
            raise ServiceError("Deepgram API key not configured")

        params = {
            "language": self.language,
            "model": self.model,
            "encoding": self.encoding,
            "sample_rate": str(self.sample_rate),
            "channels": str(self.channels),
            "punctuate": str(self.punctuate).lower(),
            "numerals": str(self.numerals).lower(),
            "profanity_filter": str(self.profanity_filter).lower(),
            "interim_results": str(self.interim_results).lower(),
        }
        url = f"{self.url}?{urllib.parse.urlencode(params)}"
        headers = {"Authorization": f"Token {deepgram_config.API_KEY}"}

        logger.info(
            "Connecting to Deepgram (%s) [mode=%s, sample_rate=%s, recording_rate=%s]",
            url,
            mode,
            self.sample_rate,
            self.recording_sample_rate,
        )
        logger.debug("Deepgram request params: %s", params)

        transcription: str = ""
        try:
            async with connect(
                url, additional_headers=headers, ping_interval=None
            ) as dg_client:
                keepalive_state = KeepAliveState()
                send_task = asyncio.create_task(
                    send_audio_chunks(
                        audio_source,
                        dg_client,
                        recording_sample_rate=self.recording_sample_rate,
                        target_sample_rate=self.sample_rate,
                        keepalive_state=keepalive_state,
                    )
                )
                receive_task = asyncio.create_task(
                    receive_transcription(dg_client, manager, mode)
                )
                keepalive_task = asyncio.create_task(
                    send_keepalive_messages(
                        dg_client,
                        keepalive_state,
                        interval_seconds=5.0,
                        max_silence_seconds=30.0,
                    )
                )

                try:
                    _, transcription = await asyncio.gather(send_task, receive_task)
                finally:
                    keepalive_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await keepalive_task
                    for task in (send_task, receive_task):
                        if not task.done():
                            task.cancel()
                            with suppress(asyncio.CancelledError):
                                await task
        except InvalidStatus as exc:  # pragma: no cover - network branch
            status_code = getattr(exc, "status_code", "unknown")
            logger.error("Deepgram connection failed (HTTP %s): %s", status_code, exc)
            await manager.send_to_queues(
                {"type": "error", "content": "Speech recognition service unavailable", "stage": "connection"}
            )
            raise ServiceError(f"Deepgram connection failed: {exc}") from exc
        except ConnectionClosedError as exc:  # pragma: no cover - network branch
            logger.error(
                "Deepgram connection closed unexpectedly (code=%s, reason='%s')",
                getattr(exc, "code", "unknown"),
                getattr(exc, "reason", ""),
            )
            error_msg = "Speech recognition interrupted"
            if getattr(exc, "code", None) == 1011:
                error_msg = "No audio detected - please ensure microphone is working"
            await manager.send_to_queues(
                {"type": "error", "content": error_msg, "stage": "transcription"}
            )
            raise ServiceError(f"Transcription failed: {error_msg}") from exc
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error during Deepgram transcription: %s", exc, exc_info=True)
            await manager.send_to_queues(
                {"type": "error", "content": "Speech recognition error", "stage": "transcription"}
            )
            raise ServiceError(f"Transcription failed: {exc}") from exc

        logger.info(
            "Deepgram transcription finished (mode=%s, chars=%s)",
            mode,
            len(transcription),
        )
        return transcription


__all__ = ["DeepgramSpeechProvider"]
