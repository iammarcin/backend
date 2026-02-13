"""Utilities for resolving ElevenLabs realtime configuration.

This module translates the validated :class:`~features.tts.schemas.requests.TTSUserSettings`
instance coming from the websocket client into a concrete
``ElevenLabsRealtimeSettings`` object.  The dataclass captures all parameters the
ElevenLabs realtime API expects, while keeping default selection logic neatly
isolated from the websocket endpoint itself.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List

from config.tts.providers import elevenlabs as elevenlabs_config
from features.tts.schemas.requests import TTSUserSettings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ElevenLabsRealtimeSettings:
    """Resolved ElevenLabs realtime configuration."""

    model: str
    voice: str
    audio_format: str
    chunk_schedule: List[int]
    stability: float
    similarity_boost: float
    style: float
    speaker_boost: bool
    inactivity_timeout: int


def resolve_realtime_settings(settings: TTSUserSettings) -> ElevenLabsRealtimeSettings:
    """Build :class:`ElevenLabsRealtimeSettings` from the websocket payload.

    Parameters
    ----------
    settings:
        Pydantic model validated from the ``user_settings`` payload supplied by the
        websocket client.
    """

    provider_settings = settings.tts

    model = provider_settings.model or elevenlabs_config.DEFAULT_MODEL
    voice = provider_settings.voice or elevenlabs_config.DEFAULT_VOICE_ID
    audio_format = provider_settings.format or elevenlabs_config.DEFAULT_REALTIME_FORMAT

    chunk_schedule = provider_settings.chunk_schedule or elevenlabs_config.DEFAULT_CHUNK_SCHEDULE
    if len(chunk_schedule) != 4:
        logger.debug(
            "Invalid chunk schedule length (%s); falling back to default", chunk_schedule
        )
        chunk_schedule = elevenlabs_config.DEFAULT_CHUNK_SCHEDULE

    stability = (
        provider_settings.stability if provider_settings.stability is not None else elevenlabs_config.DEFAULT_STABILITY
    )
    similarity = (
        provider_settings.similarity_boost
        if provider_settings.similarity_boost is not None
        else elevenlabs_config.DEFAULT_SIMILARITY
    )
    style = provider_settings.style if provider_settings.style is not None else elevenlabs_config.DEFAULT_STYLE
    speaker_boost = bool(provider_settings.use_speaker_boost)

    return ElevenLabsRealtimeSettings(
        model=model,
        voice=voice,
        audio_format=audio_format,
        chunk_schedule=chunk_schedule,
        stability=stability,
        similarity_boost=similarity,
        style=style,
        speaker_boost=speaker_boost,
        inactivity_timeout=elevenlabs_config.DEFAULT_INACTIVITY_TIMEOUT,
    )