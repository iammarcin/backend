"""OpenAI text-to-speech configuration."""

from __future__ import annotations

import os
from typing import List

# Model defaults
DEFAULT_MODEL = os.getenv("OPENAI_TTS_MODEL_DEFAULT", "gpt-4o-mini-tts")

# Voice settings
DEFAULT_VOICE = "alloy"
AVAILABLE_VOICES: List[str] = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]

# Audio format
DEFAULT_AUDIO_FORMAT = "mp3"
AVAILABLE_FORMATS: List[str] = ["mp3", "opus", "aac", "flac"]

# Speed limits
DEFAULT_SPEED = 1.0
MIN_SPEED = 0.25
MAX_SPEED = 4.0

__all__ = [
    "DEFAULT_MODEL",
    "DEFAULT_VOICE",
    "AVAILABLE_VOICES",
    "DEFAULT_AUDIO_FORMAT",
    "AVAILABLE_FORMATS",
    "DEFAULT_SPEED",
    "MIN_SPEED",
    "MAX_SPEED",
]
