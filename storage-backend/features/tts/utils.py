"""Utility helpers shared across TTS services and providers."""

from __future__ import annotations

import io
import logging
import re
import wave
from datetime import UTC, datetime
from typing import Iterable, List, Tuple

logger = logging.getLogger(__name__)

_ACTION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\*burps loudly\*",
        r"\*belches\*",
        r"\*burps\*",
        r"\*laughs maniacally\*",
        r"\*takes a swig from flask\*",
        r"<response>",
        r"</response>",
    )
]


def tune_text(text: str) -> str:
    """Normalise text before sending it to TTS providers."""

    if not text:
        return ""

    tuned = text.replace(",", ".. …")
    tuned = tuned.replace("?!", "??")
    tuned = tuned.replace("*", "")

    tuned = re.sub(r"([a-zA-Z])\. ", r"\1.. ", tuned)
    tuned = re.sub(r"([a-zA-Z])! ", r"\1!!.. ", tuned)
    tuned = re.sub(r"([a-zA-Z])\? ", r"\1??.. ", tuned)

    for pattern in _ACTION_PATTERNS:
        tuned = pattern.sub("", tuned)

    tuned = re.sub(r"<inner_monologue>.*?</inner_monologue>", "", tuned, flags=re.DOTALL)
    tuned = re.sub(r"\b(burps loudly|belches|burps|laughs maniacally|takes a swig from flask)\b", "", tuned, flags=re.IGNORECASE)
    return tuned.strip()


def split_text_for_tts(text: str, max_chars: int = 4096) -> List[str]:
    """Split text into manageable chunks respecting sentence boundaries."""

    if len(text) <= max_chars:
        return [text]

    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: List[str] = []
    current = ""

    for sentence in sentences:
        if not sentence:
            continue
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) > max_chars:
            if current:
                chunks.append(current)
                current = sentence
            elif len(sentence) > max_chars:
                start = 0
                while start < len(sentence):
                    chunks.append(sentence[start : start + max_chars])
                    start += max_chars
                current = ""
            else:
                current = sentence
        else:
            current = candidate

    if current:
        chunks.append(current)

    return chunks


_FORMAT_MEDIA_TYPES = {
    "mp3": "audio/mpeg",
    "mpeg": "audio/mpeg",
    "wav": "audio/wav",
    "wave": "audio/wav",
    "ogg": "audio/ogg",
    "opus": "audio/ogg",
    "pcm": "audio/L16",
    "pcm_16000": "audio/L16;rate=16000;channels=1",
    "pcm_22050": "audio/L16;rate=22050;channels=1",
    "pcm_24000": "audio/L16;rate=24000;channels=1",
    "pcm_44100": "audio/L16;rate=44100;channels=1",
}


def _parse_pcm_sample_rate(audio_format: str) -> int:
    """Extract a sample rate from pcm-style format strings."""

    try:
        if "_" in audio_format:
            return int(audio_format.split("_", 1)[1])
        return 24000
    except ValueError:
        logger.debug("Falling back to default sample rate for format: %s", audio_format)
        return 24000


def prepare_audio_payload(audio_bytes: bytes, audio_format: str | None) -> Tuple[bytes, str, str, dict[str, int | str]]:
    """Normalise raw provider audio into a storable/uploadable payload."""

    resolved_format = (audio_format or "mp3").lower()
    metadata: dict[str, int | str] = {}

    if resolved_format.startswith("pcm"):
        sample_rate = _parse_pcm_sample_rate(resolved_format)
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_bytes)
        wav_buffer.seek(0)
        metadata = {"original_format": resolved_format, "sample_rate": sample_rate}
        return wav_buffer.read(), "wav", "audio/wav", metadata

    return (
        audio_bytes,
        resolved_format,
        audio_format_to_mime(resolved_format),
        metadata,
    )


def merge_audio_chunks(chunks: Iterable[bytes], output_format: str = "mp3") -> bytes:
    """Merge provider audio chunks into a single payload."""

    data = list(chunks)
    if not data:
        return b""

    if output_format == "mp3":
        try:
            from pydub import AudioSegment  # type: ignore import

            merged = AudioSegment.empty()
            for chunk in data:
                merged += AudioSegment.from_file(io.BytesIO(chunk), format="mp3")
            buffer = io.BytesIO()
            merged.export(buffer, format="mp3")
            buffer.seek(0)
            return buffer.read()
        except ImportError:
            logger.warning("pydub not installed; falling back to naive MP3 concatenation")

    return b"".join(data)


def convert_timestamp_to_date(value: object) -> str | None:
    """Convert a timestamp into an ISO formatted datetime string."""

    if value in (None, ""):
        return None
    try:
        timestamp = float(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat()


def audio_format_to_mime(audio_format: str | None) -> str:
    """Return an appropriate media type for the supplied audio format."""

    if not audio_format:
        return "application/octet-stream"

    key = str(audio_format).lower()
    return _FORMAT_MEDIA_TYPES.get(key, "application/octet-stream")


__all__ = [
    "audio_format_to_mime",
    "convert_timestamp_to_date",
    "merge_audio_chunks",
    "prepare_audio_payload",
    "split_text_for_tts",
    "tune_text",
]
