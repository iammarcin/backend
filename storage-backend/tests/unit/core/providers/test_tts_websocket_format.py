"""Unit tests covering websocket format selection for TTS providers."""

from __future__ import annotations

import importlib
import types

import pytest

from core.providers.tts_base import BaseTTSProvider, TTSRequest, TTSResult
from core.providers.tts import elevenlabs as elevenlabs_module
from core.providers.tts import openai as openai_module
from config.tts.providers import elevenlabs as elevenlabs_config


class _TestProvider(BaseTTSProvider):
    name = "test"

    async def generate(self, request: TTSRequest) -> TTSResult:  # pragma: no cover - unused
        return TTSResult(
            audio_bytes=b"",
            provider=self.name,
            model="dummy",
            format="mp3",
        )


def test_base_provider_default_format() -> None:
    """Base provider should default to raw PCM when streaming over websockets."""

    provider = _TestProvider()

    assert provider.get_websocket_format() == "pcm"


def test_openai_provider_format(monkeypatch: pytest.MonkeyPatch) -> None:
    """OpenAI provider explicitly reports the PCM websocket format."""

    dummy_client = types.SimpleNamespace()
    monkeypatch.setattr(openai_module, "get_openai_client", lambda: dummy_client)

    provider = openai_module.OpenAITTSProvider()

    assert provider.get_websocket_format() == "pcm"


def test_elevenlabs_provider_format(monkeypatch: pytest.MonkeyPatch) -> None:
    """ElevenLabs provider specifies the required 24 kHz PCM websocket format."""

    monkeypatch.setattr(elevenlabs_config, "API_KEY", "test-key", raising=False)
    monkeypatch.setattr(elevenlabs_config, "DEFAULT_MODEL", "test-model", raising=False)
    importlib.reload(elevenlabs_module)

    provider = elevenlabs_module.ElevenLabsTTSProvider()

    assert provider.get_websocket_format() == "pcm_24000"
