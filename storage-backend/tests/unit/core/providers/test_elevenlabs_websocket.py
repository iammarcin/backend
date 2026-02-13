"""Unit tests covering ElevenLabs WebSocket helper behaviour."""

from __future__ import annotations

import importlib

import pytest

from core.providers.tts import elevenlabs as elevenlabs_module
from config.tts.providers import elevenlabs as elevenlabs_config


@pytest.fixture()
def provider(monkeypatch: pytest.MonkeyPatch) -> elevenlabs_module.ElevenLabsTTSProvider:
    """Construct an ElevenLabs provider with configuration patched for tests."""

    monkeypatch.setattr(elevenlabs_config, "API_KEY", "test-key", raising=False)
    monkeypatch.setattr(elevenlabs_config, "DEFAULT_MODEL", "test-model", raising=False)
    importlib.reload(elevenlabs_module)

    return elevenlabs_module.ElevenLabsTTSProvider()


def test_provider_exposes_websocket_stream(provider: elevenlabs_module.ElevenLabsTTSProvider) -> None:
    """Ensure the ElevenLabs provider exposes the websocket streaming API."""

    assert hasattr(provider, "stream_websocket")
    assert callable(getattr(provider, "stream_websocket"))


def test_websocket_format_mapping() -> None:
    """Verify the websocket format mapping contains the expected aliases."""

    mapping = elevenlabs_module._FORMAT_TO_WEBSOCKET_FORMAT

    assert "pcm" in mapping
    assert mapping["pcm"] == "pcm_24000"
    assert "pcm_24000" in mapping
    assert mapping["pcm_24000"] == "pcm_24000"
    assert "mp3" in mapping
    assert mapping["mp3"] == "mp3_44100_128"


def test_chunk_length_schedule_parsing(provider: elevenlabs_module.ElevenLabsTTSProvider) -> None:
    """Validate ``chunk_length_schedule`` parsing for multiple input types."""

    assert provider._parse_chunk_length_schedule([120, 160, 250, 290]) == [120, 160, 250, 290]
    assert provider._parse_chunk_length_schedule(100) == [100, 100, 100, 100]
    assert provider._parse_chunk_length_schedule("[50, 50, 50, 50]") == [50, 50, 50, 50]

    default_schedule = provider._parse_chunk_length_schedule(None)
    assert len(default_schedule) == 4
    assert all(isinstance(item, int) for item in default_schedule)

    invalid_schedule = provider._parse_chunk_length_schedule("invalid")
    assert len(invalid_schedule) == 4
    assert all(isinstance(item, int) for item in invalid_schedule)
