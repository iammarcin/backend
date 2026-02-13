"""Audio configuration - prompts, models, and defaults."""

from __future__ import annotations

from .defaults import (
    DEFAULT_TRANSCRIBE_MODEL,
    DEFAULT_TRANSLATE_MODEL,
    DEFAULT_TRANSCRIBE_PROVIDER,
    DEFAULT_TRANSLATE_PROVIDER,
    DEEPGRAM_MODEL_ALIASES,
    GEMINI_SPEECH_MODEL_ALIASES,
    OPENAI_SPEECH_MODEL_ALIASES,
    StreamingProviderSettings,
    is_openai_streaming_model,
    normalise_deepgram_model,
)
from .models import GEMINI_SPEECH_MODEL_ALIASES as GEMINI_MODEL_ALIASES
from .prompts import DEFAULT_TRANSCRIBE_PROMPT, DEFAULT_TRANSLATE_PROMPT
from . import providers

def get_streaming_available_models():
    """Lazy import of STREAMING_AVAILABLE_MODELS to avoid circular imports."""
    from .defaults import STREAMING_AVAILABLE_MODELS
    return STREAMING_AVAILABLE_MODELS

__all__ = [
    "DEFAULT_TRANSCRIBE_MODEL",
    "DEFAULT_TRANSLATE_MODEL",
    "DEFAULT_TRANSCRIBE_PROVIDER",
    "DEFAULT_TRANSLATE_PROVIDER",
    "DEFAULT_TRANSCRIBE_PROMPT",
    "DEFAULT_TRANSLATE_PROMPT",
    "DEEPGRAM_MODEL_ALIASES",
    "GEMINI_MODEL_ALIASES",
    "GEMINI_SPEECH_MODEL_ALIASES",
    "OPENAI_SPEECH_MODEL_ALIASES",
    "StreamingProviderSettings",
    "is_openai_streaming_model",
    "normalise_deepgram_model",
    "providers",
]
