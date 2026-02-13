"""Text-to-speech configuration."""

from __future__ import annotations

from .defaults import (
    DEFAULT_AUDIO_FORMAT,
    DEFAULT_PROVIDER,
    DEFAULT_QUALITY,
    TTSSettings,
    VOICE_REGISTRY,
)
from . import providers

__all__ = [
    "DEFAULT_PROVIDER",
    "DEFAULT_AUDIO_FORMAT",
    "DEFAULT_QUALITY",
    "TTSSettings",
    "VOICE_REGISTRY",
    "providers",
]
