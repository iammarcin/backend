"""Audio provider configuration helpers."""

from __future__ import annotations

from config.audio import DEFAULT_TRANSCRIBE_PROMPT, DEFAULT_TRANSLATE_PROMPT
from config.audio.utils import get_gemini_default_model, normalise_gemini_model


def get_transcription_prompt(user_prompt: str | None = None) -> str:
    """Return the prompt used for transcription providers."""

    return user_prompt or DEFAULT_TRANSCRIBE_PROMPT


def get_translation_prompt(
    language: str | None = None,
    user_prompt: str | None = None,
) -> str:
    """Return the prompt used for translation providers."""

    if user_prompt:
        return user_prompt
    target_language = language or "English"
    return DEFAULT_TRANSLATE_PROMPT.format(language=target_language)


__all__ = [
    "get_gemini_default_model",
    "normalise_gemini_model",
    "get_transcription_prompt",
    "get_translation_prompt",
]
