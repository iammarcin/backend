"""Google Gemini Live configuration."""

from __future__ import annotations

# Model defaults
DEFAULT_MODEL = "models/gemini-2.0-flash-exp"

# Audio settings
DEFAULT_SAMPLE_RATE = 16_000  # Hz
SUPPORTED_SAMPLE_RATES = [16_000, 24_000]

# Voice settings
DEFAULT_VOICE = "Puck"
AVAILABLE_VOICES = ["Puck", "Charon", "Kore", "Fenrir", "Aoede"]

# Response generation defaults
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 1024

__all__ = [
    "DEFAULT_MODEL",
    "DEFAULT_SAMPLE_RATE",
    "SUPPORTED_SAMPLE_RATES",
    "DEFAULT_VOICE",
    "AVAILABLE_VOICES",
    "DEFAULT_TEMPERATURE",
    "DEFAULT_MAX_TOKENS",
]
