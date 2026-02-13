"""Utilities for validating, uploading, and translating realtime audio."""

from __future__ import annotations

import io
import logging
import wave
from dataclasses import dataclass
from typing import Callable

from fastapi import WebSocket

from core.exceptions import ServiceError
from core.streaming.manager import StreamingManager
from features.audio.schemas import (
    AudioAction,
    StaticTranscriptionUserInput,
    StaticTranscriptionUserSettings,
)
from features.audio.service import STTService
from features.realtime.schemas import RealtimeSessionSettings

from .context import RealtimeTurnContext
from infrastructure.aws.storage import StorageService
from .event_factory import RealtimeEventFactory

from .errors import (
    audio_format_error,
    audio_upload_failed_error,
    translation_failed_error,
)
from .utils import is_google_model
from .validation import AudioValidationError, validate_audio_format

logger = logging.getLogger(__name__)

_PCM16_MIN_BYTES = 24_000 * 2  # One second of mono PCM16 audio


@dataclass(slots=True)
class AudioProcessingResult:
    """Results from processing realtime audio for a turn."""

    audio_url: str | None = None
    translation_text: str | None = None


@dataclass(slots=True)
class RealtimeAudioFinaliser:
    """Handle realtime audio validation, upload, and translation."""

    storage_service_factory: Callable[[], StorageService]
    stt_service_factory: Callable[[], STTService]
    streaming_manager: StreamingManager
    event_factory: RealtimeEventFactory

    def _convert_pcm_to_wav(self, pcm_bytes: bytes, sample_rate: int = 24000) -> bytes:
        """Convert raw PCM16 audio to WAV format.

        Args:
            pcm_bytes: Raw PCM16 audio data
            sample_rate: Sample rate in Hz (default 24000 for OpenAI realtime)

        Returns:
            WAV formatted audio bytes
        """
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_bytes)
        wav_buffer.seek(0)
        return wav_buffer.read()

    async def process_audio(
        self,
        *,
        turn_context: RealtimeTurnContext,
        settings: RealtimeSessionSettings,
        websocket: WebSocket,
        session_id: str,
        customer_id: int,
    ) -> AudioProcessingResult:
        """Validate, upload, and optionally translate the turn audio."""

        audio_bytes = turn_context.audio_bytes()
        if not audio_bytes:
            return AudioProcessingResult()

        if not await self._validate_audio(
            audio_bytes=audio_bytes,
            websocket=websocket,
            session_id=session_id,
        ):
            return AudioProcessingResult()

        audio_url = await self._upload_audio(
            audio_bytes=audio_bytes,
            customer_id=customer_id,
            websocket=websocket,
            session_id=session_id,
        )

        translation_text: str | None = None
        if audio_url and self._should_translate(settings):
            translation_text = await self._translate_audio(
                audio_bytes=audio_bytes,
                customer_id=customer_id,
                settings=settings,
                websocket=websocket,
                session_id=session_id,
            )
            if translation_text:
                turn_context.live_translation_text = translation_text
                self.streaming_manager.collect_chunk(
                    translation_text, "translation"
                )
                await websocket.send_json(
                    {
                        "type": "realtime.translation",
                        "session_id": session_id,
                        "text": translation_text,
                        "language": settings.translation_language,
                    }
                )

        return AudioProcessingResult(audio_url=audio_url, translation_text=translation_text)

    async def _validate_audio(
        self,
        *,
        audio_bytes: bytes,
        websocket: WebSocket,
        session_id: str,
    ) -> bool:
        try:
            validate_audio_format(audio_bytes, expected_format="pcm16")
            logger.info(
                "Realtime audio validation passed", extra={"bytes": len(audio_bytes)}
            )
        except AudioValidationError as exc:
            if len(audio_bytes) < _PCM16_MIN_BYTES:
                logger.warning(
                    "Bypassing strict audio validation for short realtime sample",
                    extra={"bytes": len(audio_bytes), "error": str(exc)},
                )
            else:
                error = audio_format_error(str(exc))
                logger.error(error.to_log_message())
                await websocket.send_json(
                    {**error.to_client_payload(), "session_id": session_id}
                )
                return False
        return True

    async def _upload_audio(
        self,
        *,
        audio_bytes: bytes,
        customer_id: int,
        websocket: WebSocket,
        session_id: str,
    ) -> str | None:
        try:
            # Convert PCM to WAV format before uploading
            wav_bytes = self._convert_pcm_to_wav(audio_bytes)
            storage = self.storage_service_factory()
            return await storage.upload_audio(
                audio_bytes=wav_bytes,
                customer_id=customer_id,
                file_extension="wav",
                folder="assets/realtime",
                content_type="audio/wav",
            )
        except Exception as exc:  # pragma: no cover - surfaced via websocket message
            error = audio_upload_failed_error(str(exc))
            logger.error(error.to_log_message())
            await websocket.send_json(
                {**error.to_client_payload(), "session_id": session_id}
            )
            return None

    def _should_translate(self, settings: RealtimeSessionSettings) -> bool:
        return (
            settings.live_translation
            and is_google_model(settings.model)
            and not settings.return_test_data
        )

    async def _translate_audio(
        self,
        *,
        audio_bytes: bytes,
        customer_id: int,
        settings: RealtimeSessionSettings,
        websocket: WebSocket,
        session_id: str,
    ) -> str | None:
        try:
            service = self.stt_service_factory()
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Failed to initialise STT service: %s", exc)
            return None

        if settings.return_test_data:
            return f"Test translation for customer {customer_id}."

        user_input = StaticTranscriptionUserInput()
        user_settings = StaticTranscriptionUserSettings()
        user_settings.general.return_test_data = False
        if settings.translation_language:
            user_settings.speech.language = settings.translation_language

        try:
            result = await service.transcribe_file(
                action=AudioAction.TRANSLATE,
                customer_id=customer_id,
                file_bytes=audio_bytes,
                content_type="audio/pcm",
                user_input=user_input,
                user_settings=user_settings,
            )
        except ServiceError as exc:
            error = translation_failed_error(str(exc))
            logger.warning(error.to_log_message())
            await websocket.send_json(
                {**error.to_client_payload(), "session_id": session_id}
            )
            return None
        except Exception as exc:  # pragma: no cover - defensive
            error = translation_failed_error(str(exc))
            logger.warning(error.to_log_message(), exc_info=True)
            await websocket.send_json(
                {**error.to_client_payload(), "session_id": session_id}
            )
            return None

        if getattr(result, "status", "") == "completed":
            translated_text = getattr(result, "result", "")
            if translated_text:
                return str(translated_text)
        return None


__all__ = ["AudioProcessingResult", "RealtimeAudioFinaliser"]
