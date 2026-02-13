"""Tests for audio streaming settings integration with the OpenAI registry."""

from __future__ import annotations

from config.audio import is_openai_streaming_model


def test_is_openai_streaming_model_detects_registry_models() -> None:
    """Registry-backed helper should identify OpenAI transcription models."""

    assert is_openai_streaming_model("gpt-4o-transcribe") is True
    assert is_openai_streaming_model("gpt-4o-mini-transcribe") is True
    # Should be case insensitive
    assert is_openai_streaming_model("GPT-4O-TRANSCRIBE") is True


def test_is_openai_streaming_model_rejects_non_transcription_models() -> None:
    """Helper should reject models that are not OpenAI streaming transcription."""

    assert is_openai_streaming_model("gpt-4o") is False
    assert is_openai_streaming_model("whisper-1") is False
    assert is_openai_streaming_model("gpt-realtime") is False
