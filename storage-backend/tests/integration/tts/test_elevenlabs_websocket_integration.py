"""Integration tests for ElevenLabs websocket streaming implementation."""

from __future__ import annotations

import asyncio
import base64
import importlib
from typing import Iterable, List
from unittest.mock import patch

import pytest
import websockets

from core.exceptions import ProviderError
from core.providers.tts_base import TTSRequest
from core.providers.tts import elevenlabs as elevenlabs_module
from config.tts.providers import elevenlabs as elevenlabs_config


class _DummyWebSocket:
    """Simple async context manager mimicking ElevenLabs websocket responses."""

    def __init__(self, messages: Iterable[str]):
        self._messages = list(messages)
        self.sent_messages: List[str] = []

    async def __aenter__(self) -> "_DummyWebSocket":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    async def send(self, message: str) -> None:
        self.sent_messages.append(message)

    def __aiter__(self):
        async def _iterator():
            for message in self._messages:
                await asyncio.sleep(0)
                yield message

        return _iterator()


@pytest.fixture(autouse=True)
def configure_elevenlabs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch ElevenLabs configuration so the provider can be instantiated."""

    monkeypatch.setattr(elevenlabs_config, "API_KEY", "test-key", raising=False)
    monkeypatch.setattr(elevenlabs_config, "DEFAULT_MODEL", "test-model", raising=False)
    importlib.reload(elevenlabs_module)


def test_websocket_streaming_integration() -> None:
    """Stream audio chunks over the websocket and decode them correctly."""

    mock_messages = [
        '{"audio": "' + base64.b64encode(b"testaudio1").decode() + '", "status": "generating"}',
        '{"audio": "' + base64.b64encode(b"testaudio2").decode() + '", "status": "generating"}',
        '{"audio": "' + base64.b64encode(b"testaudio3").decode() + '", "status": "generating"}',
        '{"status": "finished"}',
    ]

    dummy_socket = _DummyWebSocket(mock_messages)

    async def _run_test() -> List[bytes]:
        with patch.object(elevenlabs_module.websockets, "connect", return_value=dummy_socket):
            provider = elevenlabs_module.ElevenLabsTTSProvider()
            request = TTSRequest(
                text="Test text for streaming",
                customer_id=1,
                format="pcm",
                voice="sherlock",
            )

            chunks: List[bytes] = []
            async for chunk in provider.stream_websocket(request):
                chunks.append(chunk)

        return chunks

    chunks = asyncio.run(_run_test())

    assert chunks == [b"testaudio1", b"testaudio2", b"testaudio3"]
    assert len(dummy_socket.sent_messages) >= 3  # initial config, text, eos


def test_websocket_error_handling() -> None:
    """Ensure websocket failures are surfaced as provider errors."""

    async def _run_test() -> None:
        class _FailingWebSocket:
            async def __aenter__(self):
                raise websockets.exceptions.WebSocketException("connection failed")

            async def __aexit__(self, exc_type, exc, tb):
                return False

        with patch.object(elevenlabs_module.websockets, "connect", return_value=_FailingWebSocket()):
            provider = elevenlabs_module.ElevenLabsTTSProvider()
            request = TTSRequest(text="Test", customer_id=7, format="pcm", voice="sherlock")

            with pytest.raises(ProviderError) as exc_info:
                async for _ in provider.stream_websocket(request):
                    pass

        assert "WebSocket" in str(exc_info.value)

    asyncio.run(_run_test())
