from __future__ import annotations

import pytest

from features.audio.schemas import AudioAction, StaticTranscriptionUserSettings
from features.audio.static_support import build_provider_settings, infer_provider


def test_infer_provider_falls_back_from_deepgram_for_static() -> None:
    """Static actions should not resolve to Deepgram provider."""

    result = infer_provider(
        "deepgram-nova-3", default="gemini", action=AudioAction.TRANSCRIBE
    )

    assert result == "gemini"


def test_infer_provider_prefers_openai_for_gpt_models() -> None:
    """OpenAI transcription models must stay mapped to OpenAI provider."""

    result = infer_provider(
        "gpt-4o-transcribe", default="gemini", action=AudioAction.TRANSCRIBE
    )

    assert result == "openai"


def test_build_provider_settings_uses_environment_gemini_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When no model is provided, choose environment-appropriate Gemini model."""

    monkeypatch.setenv("NODE_ENV", "production")
    production_settings = build_provider_settings(
        action=AudioAction.TRANSCRIBE,
        user_settings=StaticTranscriptionUserSettings(),
    )

    assert production_settings["provider"] == "gemini"
    assert production_settings["model"] == "gemini-2.5-pro"

    monkeypatch.setenv("NODE_ENV", "local")
    local_settings = build_provider_settings(
        action=AudioAction.TRANSCRIBE,
        user_settings=StaticTranscriptionUserSettings(),
    )

    assert local_settings["provider"] == "gemini"
    assert local_settings["model"] == "gemini-2.5-flash"


def test_build_provider_settings_converts_deepgram_to_gemini_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deepgram static requests should normalise to a supported Gemini model."""

    monkeypatch.setenv("NODE_ENV", "local")
    provider_settings = build_provider_settings(
        action=AudioAction.TRANSCRIBE,
        user_settings=StaticTranscriptionUserSettings(
            speech={"model": "deepgram-nova-3"}
        ),
    )

    assert provider_settings["provider"] == "gemini"
    assert provider_settings["model"] == "gemini-2.5-flash"
