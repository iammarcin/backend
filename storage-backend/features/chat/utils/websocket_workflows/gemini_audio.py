"""Audio preparation helpers for Gemini workflows."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict

logger = logging.getLogger(__name__)

DEFAULT_RECORDING_SAMPLE_RATE = 24_000
TARGET_SAMPLE_RATE = 16_000


@dataclass(slots=True)
class PreparedAudio:
    """Container describing audio payloads ready for Gemini."""

    pcm_bytes: bytes
    wav_bytes: bytes
    recording_sample_rate: int
    target_sample_rate: int


async def prepare_audio_for_gemini(
    *,
    audio_buffer: bytearray,
    settings: Dict[str, Any],
    timings: Dict[str, float],
) -> PreparedAudio:
    """Resample and convert raw audio into WAV for Gemini consumption."""

    speech_settings = settings.get("speech", {}) if isinstance(settings, dict) else {}
    try:
        recording_sample_rate = int(
            speech_settings.get("recording_sample_rate", DEFAULT_RECORDING_SAMPLE_RATE)
            or DEFAULT_RECORDING_SAMPLE_RATE
        )
    except (TypeError, ValueError):  # pragma: no cover - defensive fallback
        recording_sample_rate = DEFAULT_RECORDING_SAMPLE_RATE

    timings["audio_resample_start"] = time.time()

    audio_bytes = bytes(audio_buffer)
    if recording_sample_rate != TARGET_SAMPLE_RATE:
        from features.audio.utils import resample_audio

        logger.info(
            "Resampling audio: %sHz → %sHz",
            recording_sample_rate,
            TARGET_SAMPLE_RATE,
        )

        audio_bytes = resample_audio(
            audio_bytes,
            recording_sample_rate,
            TARGET_SAMPLE_RATE,
        )

    timings["audio_resample_end"] = time.time()

    timings["audio_conversion_start"] = time.time()
    wav_data = await _convert_pcm_to_wav(
        audio_bytes,
        sample_rate=TARGET_SAMPLE_RATE,
        channels=1,
    )
    timings["audio_conversion_end"] = time.time()

    logger.info(
        "Audio prepared: PCM=%s bytes, WAV=%s bytes",
        len(audio_bytes),
        len(wav_data),
    )

    return PreparedAudio(
        pcm_bytes=audio_bytes,
        wav_bytes=wav_data,
        recording_sample_rate=recording_sample_rate,
        target_sample_rate=TARGET_SAMPLE_RATE,
    )


async def _convert_pcm_to_wav(
    audio_bytes: bytes,
    *,
    sample_rate: int,
    channels: int,
) -> bytes:
    """Convert PCM audio bytes into a WAV container in a worker thread."""

    def _convert() -> bytes:
        import wave
        from io import BytesIO

        wav_buffer = BytesIO()

        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(2)  # 16-bit samples
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_bytes)

        wav_buffer.seek(0)
        return wav_buffer.read()

    return await asyncio.to_thread(_convert)


__all__ = ["PreparedAudio", "prepare_audio_for_gemini", "_convert_pcm_to_wav"]

