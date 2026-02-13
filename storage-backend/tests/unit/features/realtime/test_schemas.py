"""Tests for realtime feature schemas."""

from __future__ import annotations

from features.realtime.schemas import RealtimeSessionSettings


def test_model_alias_normalisation() -> None:
    settings = RealtimeSessionSettings(model="openai-realtime")

    assert settings.model == "gpt-realtime"


def test_from_user_settings_uses_text_model() -> None:
    payload = {"text": {"model": "openai-realtime"}}

    settings = RealtimeSessionSettings.from_user_settings(payload)

    assert settings.model == "gpt-realtime"


def test_from_user_settings_prioritises_realtime_model() -> None:
    payload = {
        "text": {"model": "gpt-realtime"},
        "realtime": {"model": "gpt-4o-realtime"},
    }

    settings = RealtimeSessionSettings.from_user_settings(payload)

    assert settings.model == "gpt-realtime"
