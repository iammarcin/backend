"""OpenAI Realtime API streaming speech provider implementation."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from typing import Any, AsyncIterator, Mapping

from websockets.asyncio.client import ClientConnection

try:
    from websockets.exceptions import InvalidStatus
except ImportError:  # pragma: no cover - backwards compatibility
    from websockets.exceptions import InvalidStatusCode as InvalidStatus

from config.audio.providers import openai as openai_config
from config.api_keys import OPENAI_API_KEY
from core.exceptions import ProviderError, ServiceError
from core.providers.audio.base import (
    BaseAudioProvider,
    SpeechProviderRequest,
    SpeechTranscriptionResult,
)
from core.streaming.manager import StreamingManager

from .utils import (
    connect_to_openai_realtime,
    forward_audio_chunks,
    receive_transcription_events,
)

logger = logging.getLogger(__name__)


class OpenAIStreamingSpeechProvider(BaseAudioProvider):
    """Provide OpenAI powered streaming speech to text via Realtime API."""

    name = "openai-streaming"
    streaming_capable = True
    supports_translation = False  # Not supported in transcription mode

    def __init__(self) -> None:
        self.model = openai_config.DEFAULT_TRANSCRIBE_MODEL
        self.language = "en"
        self.sample_rate = 24000  # Native rate (no resampling needed)
        self.recording_sample_rate = 24000
        self.enable_vad = True
        self.vad_threshold = 0.5
        self.vad_prefix_padding_ms = 300
        self.vad_silence_duration_ms = 500
        self.prompt = ""

    def configure(self, settings: Mapping[str, Any]) -> None:  # type: ignore[override]
        """Apply OpenAI streaming specific configuration parameters."""

        if not settings:
            return

        model = settings.get("model")
        if model:
            self.model = str(model)

        self.language = str(settings.get("language", self.language))
        self.sample_rate = int(settings.get("sample_rate", self.sample_rate))
        self.recording_sample_rate = int(
            settings.get("recording_sample_rate", self.recording_sample_rate)
        )

        if "enable_vad" in settings:
            self.enable_vad = bool(settings["enable_vad"])
        if "vad_threshold" in settings:
            self.vad_threshold = float(settings["vad_threshold"])
        if "vad_prefix_padding_ms" in settings:
            self.vad_prefix_padding_ms = int(settings["vad_prefix_padding_ms"])
        if "vad_silence_duration_ms" in settings:
            self.vad_silence_duration_ms = int(settings["vad_silence_duration_ms"])

        if "prompt" in settings:
            self.prompt = str(settings["prompt"])

        logger.info(
            "Configured OpenAI streaming provider (model=%s, language=%s, sample_rate=%s, vad=%s)",
            self.model,
            self.language,
            self.sample_rate,
            self.enable_vad,
        )

    async def transcribe_file(
        self, request: SpeechProviderRequest
    ) -> SpeechTranscriptionResult:  # pragma: no cover - not part of milestone scope
        raise ProviderError(
            "OpenAI streaming provider supports streaming transcription only. "
            "Use OpenAISpeechProvider for static files.",
            provider=self.name,
        )

    async def transcribe_stream(
        self,
        *,
        audio_source: AsyncIterator[bytes | None],
        manager: StreamingManager,
        mode: str = "non-realtime",
    ) -> str:
        """Transcribe audio stream using OpenAI Realtime API."""

        if not OPENAI_API_KEY:
            raise ServiceError("OpenAI API key not configured")

        logger.info(
            "Starting OpenAI streaming transcription (model=%s, mode=%s)",
            self.model,
            mode,
        )

        # Determine session model vs transcription model
        # Transcription models: gpt-4o-transcribe, gpt-4o-mini-transcribe
        # Session models: gpt-realtime, gpt-realtime-mini
        transcription_only = "transcribe" in self.model.lower()

        if transcription_only:
            # Transcription-only mode: use gpt-realtime as session model
            session_model = "gpt-realtime"
            transcription_model = self.model
            logger.info(
                "Transcription-only mode (session_model=%s, transcription_model=%s)",
                session_model,
                transcription_model,
            )
        else:
            # Realtime mode: use selected model as session, enable transcription
            session_model = self.model
            transcription_model = "gpt-4o-transcribe"
            logger.info(
                "Realtime mode with transcription (session_model=%s, transcription_model=%s)",
                session_model,
                transcription_model,
            )

        transcription = ""
        ws_client: ClientConnection | None = None

        try:
            ws_client = await connect_to_openai_realtime(
                model=self.model,  # DEPRECATED param
                session_model=session_model,
                transcription_model=transcription_model,
                transcription_only=transcription_only,
                language=self.language,
                prompt=self.prompt,
                enable_vad=self.enable_vad,
                vad_threshold=self.vad_threshold,
                vad_prefix_padding_ms=self.vad_prefix_padding_ms,
                vad_silence_duration_ms=self.vad_silence_duration_ms,
            )

            send_task = asyncio.create_task(
                forward_audio_chunks(
                    audio_source,
                    ws_client,
                    sample_rate=self.sample_rate,
                    transcription_only=transcription_only,
                    vad_enabled=self.enable_vad,
                )
            )
            receive_task = asyncio.create_task(
                receive_transcription_events(
                    ws_client,
                    manager,
                    mode=mode,
                    provider_name=self.name,
                )
            )

            try:
                # Wait for both tasks, but close WebSocket when sending finishes
                # to allow receiver to exit cleanly
                await send_task
                logger.debug("Audio sending complete, closing WebSocket to signal receiver")
                await ws_client.close()
                transcription = await receive_task
            finally:
                for task in (send_task, receive_task):
                    if not task.done():
                        task.cancel()
                        with suppress(asyncio.CancelledError):
                            await task

        except InvalidStatus as exc:  # pragma: no cover
            logger.error("OpenAI WebSocket connection failed: %s", exc)
            await manager.send_to_queues(
                {"type": "error", "content": f"OpenAI connection failed: {exc}"}
            )
            raise ServiceError(f"OpenAI connection failed: {exc}") from exc
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("OpenAI streaming transcription error: %s", exc, exc_info=True)
            await manager.send_to_queues(
                {"type": "error", "content": f"Transcription error: {exc}"}
            )
            raise ProviderError(
                f"OpenAI streaming transcription failed: {exc}",
                provider=self.name,
                original_error=exc,
            ) from exc
        finally:
            if ws_client:
                with suppress(Exception):
                    await ws_client.close()

        logger.info(
            "OpenAI transcription completed (mode=%s, chars=%s)",
            mode,
            len(transcription),
        )
        return transcription


__all__ = ["OpenAIStreamingSpeechProvider"]
