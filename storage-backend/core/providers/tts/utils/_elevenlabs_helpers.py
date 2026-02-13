"""Utility helpers for the ElevenLabs text-to-speech provider."""

from __future__ import annotations

import ast
import logging
from datetime import UTC, datetime
from typing import Any, Mapping

from config.tts.providers import elevenlabs as elevenlabs_config

logger = logging.getLogger(__name__)

API_BASE = "https://api.elevenlabs.io/v1"
DEFAULT_VOICE_ID = elevenlabs_config.DEFAULT_VOICE_ID
VOICE_NAME_TO_ID = dict(elevenlabs_config.VOICE_NAME_TO_ID)
KNOWN_VOICE_IDS = set(VOICE_NAME_TO_ID.values()) | {DEFAULT_VOICE_ID}

VOICE_SETTING_KEYS = ("stability", "similarity_boost", "style", "use_speaker_boost")

FORMAT_TO_WEBSOCKET_FORMAT = {
    "pcm": "pcm_24000",
    "pcm_24000": "pcm_24000",
    "mp3": "mp3_44100_128",
    "mp3_44100": "mp3_44100_128",
}


def resolve_voice(voice: str | None) -> str:
    """Return a valid ElevenLabs voice identifier for the supplied value."""

    if voice is None:
        return DEFAULT_VOICE_ID

    candidate = str(voice).strip()
    if not candidate:
        return DEFAULT_VOICE_ID

    lookup_key = candidate.lower()
    if lookup_key in VOICE_NAME_TO_ID:
        return VOICE_NAME_TO_ID[lookup_key]

    if candidate in KNOWN_VOICE_IDS:
        return candidate

    return candidate


def parse_chunk_length_schedule(value: Any) -> list[int]:
    """Parse ``chunk_length_schedule`` from configuration or metadata."""

    default = [120, 160, 250, 290]

    if value in (None, ""):
        return default

    if isinstance(value, list):
        if len(value) == 4 and all(isinstance(item, int) for item in value):
            return value
        logger.warning("Invalid chunk_length_schedule list: %s, using default", value)
        return default

    if isinstance(value, int):
        return [value] * 4

    if isinstance(value, str):
        try:
            parsed = ast.literal_eval(value)
        except (ValueError, SyntaxError):
            logger.warning("Failed to parse chunk_length_schedule: %s", value)
        else:
            if isinstance(parsed, int):
                return [parsed] * 4
            if isinstance(parsed, list) and len(parsed) == 4 and all(isinstance(item, int) for item in parsed):
                return parsed

    return default


def gather_voice_settings(
    settings: Mapping[str, Any],
    metadata: Mapping[str, Any],
    *,
    prefer_metadata_when_unset: bool,
) -> dict[str, Any]:
    """Collect voice settings from stored configuration and request metadata."""

    voice_settings: dict[str, Any] = {}
    for key in VOICE_SETTING_KEYS:
        if key in settings:
            value = settings.get(key)
            if value is not None:
                voice_settings[key] = value
            elif prefer_metadata_when_unset and metadata.get(key) is not None:
                voice_settings[key] = metadata[key]
        elif metadata.get(key) is not None:
            voice_settings[key] = metadata[key]
    return voice_settings


def ensure_websocket_defaults(voice_settings: dict[str, Any]) -> None:
    """Apply ElevenLabs defaults required for websocket streaming."""

    voice_settings.setdefault("stability", elevenlabs_config.DEFAULT_STABILITY)
    voice_settings.setdefault("similarity_boost", elevenlabs_config.DEFAULT_SIMILARITY_BOOST)
    voice_settings.setdefault("style", elevenlabs_config.DEFAULT_STYLE)
    voice_settings.setdefault("use_speaker_boost", elevenlabs_config.DEFAULT_USE_SPEAKER_BOOST)


def websocket_format_for(output_format: str) -> str:
    """Return the websocket-compatible format for an output format value."""

    return FORMAT_TO_WEBSOCKET_FORMAT.get(output_format, "pcm_24000")


def convert_timestamp_to_date(value: Any) -> str | None:
    """Convert ElevenLabs billing timestamps to ISO formatted dates."""

    if value in (None, ""):
        return None
    try:
        timestamp = float(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat()


__all__ = [
    "API_BASE",
    "DEFAULT_VOICE_ID",
    "FORMAT_TO_WEBSOCKET_FORMAT",
    "VOICE_NAME_TO_ID",
    "KNOWN_VOICE_IDS",
    "gather_voice_settings",
    "parse_chunk_length_schedule",
    "resolve_voice",
    "ensure_websocket_defaults",
    "websocket_format_for",
    "convert_timestamp_to_date",
]
