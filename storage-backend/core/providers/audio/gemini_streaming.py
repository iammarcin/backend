"""Google Gemini streaming speech provider implementation using buffered transcription."""

from __future__ import annotations

import asyncio
import logging
import time
import wave
from io import BytesIO
from typing import Any, AsyncIterator, Mapping

from google.genai import types as genai_types

from config.audio.providers import gemini as gemini_config
from core.clients.ai import get_gemini_client
from core.exceptions import ProviderError
from core.providers.audio.base import (
    BaseAudioProvider,
    SpeechProviderRequest,
    SpeechTranscriptionResult,
)
from core.providers.audio.config import normalise_gemini_model
from core.streaming.manager import StreamingManager
from core.utils.env import is_production

logger = logging.getLogger(__name__)


class GeminiStreamingSpeechProvider(BaseAudioProvider):
    """Provide Gemini powered speech to text via buffered streaming."""

    name = "gemini-streaming"
    streaming_capable = True

    def __init__(self) -> None:
        self.model = normalise_gemini_model(None, production=is_production())  # Uses default
        self.language = "en"
        self.sample_rate = gemini_config.DEFAULT_SAMPLE_RATE
        self.recording_sample_rate = gemini_config.DEFAULT_RECORDING_RATE
        self.channels = 1
        self.buffer_duration_seconds = gemini_config.DEFAULT_BUFFER_DURATION
        self.optional_prompt = ""

    def configure(self, settings: Mapping[str, Any]) -> None:  # type: ignore[override]
        """Apply Gemini streaming specific configuration parameters."""

        if not settings:
            return

        model = settings.get("model")
        if model:
            self.model = normalise_gemini_model(model, production=is_production())

        self.language = str(settings.get("language", self.language))
        self.sample_rate = int(settings.get("sample_rate", self.sample_rate))
        self.recording_sample_rate = int(
            settings.get("recording_sample_rate", self.recording_sample_rate)
        )
        self.channels = int(settings.get("channels", self.channels))

        if "buffer_duration_seconds" in settings:
            self.buffer_duration_seconds = float(settings["buffer_duration_seconds"])

        if "optional_prompt" in settings:
            self.optional_prompt = str(settings["optional_prompt"])

        logger.info(
            "Configured Gemini streaming provider (model=%s, language=%s, sample_rate=%s, recording_rate=%s, buffer_duration=%s)",
            self.model,
            self.language,
            self.sample_rate,
            self.recording_sample_rate,
            self.buffer_duration_seconds,
        )

    async def transcribe_file(
        self, request: SpeechProviderRequest
    ) -> SpeechTranscriptionResult:  # pragma: no cover - not part of milestone scope
        raise ProviderError(
            "Gemini streaming provider supports streaming transcription only. Use GeminiSpeechProvider for static files.",
            provider=self.name,
        )

    async def transcribe_stream(
        self,
        *,
        audio_source: AsyncIterator[bytes | None],
        manager: StreamingManager,
        mode: str = "non-realtime",
    ) -> str:
        """Transcribe audio stream using buffered Gemini API calls."""

        logger.info(
            "Starting Gemini buffered streaming transcription (model=%s, buffer=%ss, mode=%s)",
            self.model,
            self.buffer_duration_seconds,
            mode,
        )

        # Calculate buffer size in bytes
        bytes_per_second = self.sample_rate * self.channels * 2  # 16-bit audio
        buffer_size_bytes = int(self.buffer_duration_seconds * bytes_per_second)
        min_chunk_size = int(gemini_config.MIN_CHUNK_DURATION * bytes_per_second)

        audio_buffer = bytearray()
        full_transcription = ""
        last_transcription_time = time.time()

        try:
            async for audio_data in audio_source:
                if audio_data is None:
                    # Recording finished - process any remaining audio
                    logger.info("Received completion signal, processing final buffer")
                    if len(audio_buffer) >= min_chunk_size:
                        final_text = await self._transcribe_buffer(
                            audio_buffer, manager, mode
                        )
                        if final_text:
                            full_transcription += final_text + " "
                    break

                # Add audio data to buffer
                audio_buffer.extend(audio_data)

                # Check if we should transcribe now
                current_time = time.time()
                time_since_last = current_time - last_transcription_time
                should_transcribe = (
                    len(audio_buffer) >= buffer_size_bytes
                    or time_since_last >= self.buffer_duration_seconds
                )

                if should_transcribe and len(audio_buffer) >= min_chunk_size:
                    chunk_text = await self._transcribe_buffer(
                        audio_buffer, manager, mode
                    )
                    if chunk_text:
                        full_transcription += chunk_text + " "

                    # Reset buffer and timer
                    audio_buffer.clear()
                    last_transcription_time = current_time

            logger.info(
                "Gemini streaming transcription finished (mode=%s, chars=%s)",
                mode,
                len(full_transcription),
            )
            return full_transcription.strip()

        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error(
                "Error during Gemini streaming transcription: %s", exc, exc_info=True
            )
            await manager.send_to_queues(
                {"type": "error", "content": f"Transcription error: {exc}"}
            )
            raise ProviderError(
                f"Gemini streaming transcription failed: {exc}",
                provider=self.name,
                original_error=exc,
            ) from exc

    async def _transcribe_buffer(
        self,
        audio_buffer: bytearray,
        manager: StreamingManager,
        mode: str,
    ) -> str:
        """Transcribe a single buffer of audio using Gemini API."""

        if len(audio_buffer) == 0:
            return ""

        try:
            # Resample if needed
            if self.recording_sample_rate != self.sample_rate:
                from features.audio.deepgram_helpers import resample_audio

                audio_bytes = resample_audio(
                    bytes(audio_buffer),
                    self.recording_sample_rate,
                    self.sample_rate,
                )
            else:
                audio_bytes = bytes(audio_buffer)

            # Convert PCM to WAV format
            wav_data = await self._convert_to_wav(audio_bytes)

            # Call Gemini API (in thread to avoid blocking)
            transcription = await self._call_gemini_api(wav_data)

            # Stream result to frontend
            if transcription and mode == "non-realtime":
                await manager.send_to_queues(
                    {"type": "transcription", "content": transcription}
                )

            logger.debug(
                "Transcribed buffer (size=%s bytes, result=%s chars)",
                len(audio_buffer),
                len(transcription),
            )

            return transcription

        except Exception as exc:
            logger.error(
                "Error transcribing buffer (size=%s): %s",
                len(audio_buffer),
                exc,
                exc_info=True,
            )
            # Don't break the stream - just return empty string
            return ""

    async def _convert_to_wav(self, audio_bytes: bytes) -> bytes:
        """Convert raw PCM audio to WAV format."""

        def _convert():
            wav_buffer = BytesIO()
            with wave.open(wav_buffer, "wb") as wav_file:
                wav_file.setnchannels(self.channels)
                wav_file.setsampwidth(2)  # 16-bit = 2 bytes
                wav_file.setframerate(self.sample_rate)
                wav_file.writeframes(audio_bytes)
            wav_buffer.seek(0)
            return wav_buffer.read()

        return await asyncio.to_thread(_convert)

    async def _call_gemini_api(self, wav_data: bytes) -> str:
        """Call Gemini API to transcribe WAV audio."""

        client = get_gemini_client()

        prompt = self.optional_prompt or (
            "Generate a transcript of the speech. "
            "Rules: No timestamps. Just the text. "
            "If no speech detected, return empty string."
        )

        part = genai_types.Part.from_bytes(data=wav_data, mime_type="audio/wav")

        def _invoke():
            response = client.models.generate_content(
                model=self.model,
                contents=[prompt, part],
            )
            return getattr(response, "text", "") or ""

        try:
            text = _invoke()
            return text.strip()
        except Exception as exc:  # pragma: no cover - network failure
            logger.error("Gemini API call failed: %s", exc, exc_info=True)
            raise ProviderError(
                "Gemini API transcription failed",
                provider=self.name,
                original_error=exc,
            ) from exc


__all__ = ["GeminiStreamingSpeechProvider"]
