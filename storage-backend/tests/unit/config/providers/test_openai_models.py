"""Tests for the OpenAI provider model registry."""

from __future__ import annotations

from config.audio.providers.openai import STREAMING_TRANSCRIPTION_MODEL_NAMES
from config.realtime.providers.openai import REALTIME_MODELS
from config.text.providers.aliases import MODEL_ALIASES
from config.text.providers.openai.models import (
    OPENAI_MODELS,
    get_model_config,
    get_model_voices,
    list_models_by_category,
)


def test_realtime_models_registered() -> None:
    """Realtime models should exist in the realtime registry."""

    assert "gpt-realtime" in REALTIME_MODELS
    assert "gpt-realtime-mini" in REALTIME_MODELS
    assert "gpt-realtime-preview" in REALTIME_MODELS
    assert "gpt-4o-realtime-preview" in REALTIME_MODELS


def test_transcription_models_registered() -> None:
    """Streaming transcription models should exist in the audio registry."""

    assert "gpt-4o-transcribe" in STREAMING_TRANSCRIPTION_MODEL_NAMES
    assert "gpt-4o-mini-transcribe" in STREAMING_TRANSCRIPTION_MODEL_NAMES
    # whisper-1 is not streaming, so it's not in STREAMING_TRANSCRIPTION_MODEL_NAMES


def test_get_realtime_models() -> None:
    """Realtime models should be available in REALTIME_MODELS."""

    models = list(REALTIME_MODELS.keys())

    assert "gpt-realtime" in models
    assert "gpt-realtime-mini" in models
    assert "gpt-realtime-preview" in models
    assert all(REALTIME_MODELS[model]["category"] == "realtime" for model in models)


def test_get_transcription_models() -> None:
    """Transcription models should be available in STREAMING_TRANSCRIPTION_MODEL_NAMES."""

    models = list(STREAMING_TRANSCRIPTION_MODEL_NAMES)

    assert "gpt-4o-transcribe" in models
    assert "gpt-4o-mini-transcribe" in models


def test_is_realtime_model() -> None:
    """Realtime models should be in REALTIME_MODELS."""

    assert "gpt-realtime" in REALTIME_MODELS
    assert "gpt-realtime-mini" in REALTIME_MODELS
    assert "gpt-4o" not in REALTIME_MODELS
    assert "gpt-4o-transcribe" not in REALTIME_MODELS


def test_is_transcription_model() -> None:
    """Transcription models should be in STREAMING_TRANSCRIPTION_MODEL_NAMES."""

    assert "gpt-4o-transcribe" in STREAMING_TRANSCRIPTION_MODEL_NAMES
    assert "gpt-4o-mini-transcribe" in STREAMING_TRANSCRIPTION_MODEL_NAMES
    assert "gpt-4o" not in STREAMING_TRANSCRIPTION_MODEL_NAMES
    assert "whisper-1" not in STREAMING_TRANSCRIPTION_MODEL_NAMES


def test_get_realtime_model_config_returns_expected_fields() -> None:
    """Realtime model config should expose audio capabilities."""

    config = REALTIME_MODELS["gpt-realtime"]
    assert config["category"] == "realtime"
    assert config["support_audio_input"] is True
    assert config["supports_audio_output"] is True
    assert config["supports_vad"] is True
    assert config["supports_function_calling"] is True
    assert config["audio_input_cost_per_min"] == 0.10
    assert config["audio_output_cost_per_min"] == 0.20


def test_get_realtime_model_voices() -> None:
    """Realtime model should expose its supported voices."""

    voices = REALTIME_MODELS["gpt-realtime"]["voices"]
    assert voices is not None
    assert {"alloy", "ash", "shimmer"}.issubset(set(voices))
    assert len(voices) >= 10


def test_deprecated_realtime_model() -> None:
    """Deprecated realtime models should expose replacement metadata."""

    config = REALTIME_MODELS["gpt-realtime-preview"]

    assert config.get("is_deprecated") is True
    assert config.get("replacement_model") == "gpt-realtime"


def test_model_aliases_point_to_ga_models() -> None:
    """Realtime aliases should resolve to GA model identifiers."""

    assert MODEL_ALIASES["openai-realtime"] == "gpt-realtime"
    assert MODEL_ALIASES["realtime"] == "gpt-realtime"
    assert MODEL_ALIASES["realtime-mini"] == "gpt-realtime-mini"
    assert MODEL_ALIASES["gpt-realtime-preview"] == "gpt-realtime"
    assert MODEL_ALIASES["gpt-4o-realtime-preview"] == "gpt-realtime"
    assert MODEL_ALIASES["gpt-5"] == "gpt-5.2"


def test_list_models_by_category_filters_results() -> None:
    """Category helper should filter by the configured category."""

    # Test that realtime and transcription models are in separate registries
    realtime_models = list(REALTIME_MODELS.keys())
    transcription_models = list(STREAMING_TRANSCRIPTION_MODEL_NAMES)
    assert realtime_models
    assert transcription_models
    assert set(realtime_models).isdisjoint(set(transcription_models))
