"""Integration tests for ElevenLabs WebSocket routing helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from features.tts.service_streaming import _is_elevenlabs_provider


def test_elevenlabs_provider_detection() -> None:
    """Ensure ElevenLabs providers are identified for websocket streaming."""

    mock_elevenlabs = MagicMock()
    mock_elevenlabs.name = "elevenlabs"
    mock_elevenlabs.stream_websocket = AsyncMock()

    assert _is_elevenlabs_provider(mock_elevenlabs) is True

    mock_openai = MagicMock()
    mock_openai.name = "openai"

    assert _is_elevenlabs_provider(mock_openai) is False

    mock_unknown = MagicMock(spec=[])

    assert _is_elevenlabs_provider(mock_unknown) is False
