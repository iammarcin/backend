from __future__ import annotations

import asyncio
import base64
import importlib
from typing import AsyncIterator
from unittest.mock import patch

import pytest

from core.providers.tts import elevenlabs as elevenlabs_module
from config.tts.providers import elevenlabs as elevenlabs_config


@pytest.fixture()
def provider(monkeypatch: pytest.MonkeyPatch) -> elevenlabs_module.ElevenLabsTTSProvider:
    """Provide a configured ElevenLabs provider for queue-based streaming tests."""

    monkeypatch.setattr(elevenlabs_config, "API_KEY", "test-key", raising=False)
    monkeypatch.setattr(elevenlabs_config, "DEFAULT_MODEL", "test-model", raising=False)
    importlib.reload(elevenlabs_module)

    return elevenlabs_module.ElevenLabsTTSProvider()


@pytest.mark.asyncio()
async def test_stream_from_text_queue_basic(provider: elevenlabs_module.ElevenLabsTTSProvider) -> None:
    """Verify queue-based streaming yields base64-encoded audio chunks."""

    text_queue: asyncio.Queue[str | None] = asyncio.Queue()

    await text_queue.put("Hello ")
    await text_queue.put("world")
    await text_queue.put(None)

    async def mock_audio() -> AsyncIterator[str]:
        yield base64.b64encode(b"audio1").decode()
        yield base64.b64encode(b"audio2").decode()

    with patch(
        "core.providers.tts.elevenlabs.websocket_stream_from_queue",
        return_value=mock_audio(),
    ) as mock_stream:
        chunks: list[str] = []
        async for chunk in provider.stream_from_text_queue(text_queue=text_queue, voice="Sherlock"):
            chunks.append(chunk)

    assert len(chunks) == 2
    assert base64.b64decode(chunks[0]) == b"audio1"
    assert base64.b64decode(chunks[1]) == b"audio2"

    call_args, call_kwargs = mock_stream.call_args
    assert call_args[0] is provider
    assert call_kwargs["text_queue"] is text_queue


@pytest.mark.asyncio()
async def test_stream_from_text_queue_voice_settings(provider: elevenlabs_module.ElevenLabsTTSProvider) -> None:
    """Ensure explicit voice settings are forwarded to the websocket streamer."""

    text_queue: asyncio.Queue[str | None] = asyncio.Queue()
    await text_queue.put("Test")
    await text_queue.put(None)

    async def mock_audio() -> AsyncIterator[str]:
        yield base64.b64encode(b"audio").decode()

    voice_settings = {
        "stability": 0.9,
        "similarity_boost": 0.8,
        "style": 0.5,
        "use_speaker_boost": True,
    }

    with patch(
        "core.providers.tts.elevenlabs.websocket_stream_from_queue",
        return_value=mock_audio(),
    ) as mock_stream:
        chunks = [
            chunk
            async for chunk in provider.stream_from_text_queue(
                text_queue=text_queue,
                voice="Sherlock",
                voice_settings=voice_settings,
            )
        ]

    assert len(chunks) == 1
    call_kwargs = mock_stream.call_args.kwargs
    assert call_kwargs["voice_settings"]["stability"] == 0.9
    assert call_kwargs["voice_settings"]["similarity_boost"] == 0.8
    assert call_kwargs["voice_settings"]["style"] == 0.5
    assert call_kwargs["voice_settings"]["use_speaker_boost"] is True


@pytest.mark.asyncio()
async def test_stream_from_text_queue_custom_schedule(
    provider: elevenlabs_module.ElevenLabsTTSProvider,
) -> None:
    """Custom chunk length schedules should be forwarded without modification."""

    text_queue: asyncio.Queue[str | None] = asyncio.Queue()
    await text_queue.put("Custom schedule")
    await text_queue.put(None)

    async def mock_audio() -> AsyncIterator[str]:
        yield base64.b64encode(b"audio").decode()

    custom_schedule = [100, 150, 200, 250]

    with patch(
        "core.providers.tts.elevenlabs.websocket_stream_from_queue",
        return_value=mock_audio(),
    ) as mock_stream:
        _ = [
            chunk
            async for chunk in provider.stream_from_text_queue(
                text_queue=text_queue,
                voice="Sherlock",
                chunk_length_schedule=custom_schedule,
            )
        ]

    call_kwargs = mock_stream.call_args.kwargs
    assert call_kwargs["chunk_length_schedule"] == custom_schedule


@pytest.mark.asyncio()
async def test_stream_from_text_queue_propagates_errors(
    provider: elevenlabs_module.ElevenLabsTTSProvider,
) -> None:
    """Errors from the websocket streaming helper should bubble up."""

    text_queue: asyncio.Queue[str | None] = asyncio.Queue()
    await text_queue.put("fails")
    await text_queue.put(None)

    async def mock_audio() -> AsyncIterator[str]:
        raise RuntimeError("boom")
        yield base64.b64encode(b"unused").decode()

    with patch(
        "core.providers.tts.elevenlabs.websocket_stream_from_queue",
        return_value=mock_audio(),
    ):
        with pytest.raises(RuntimeError):
            async for _ in provider.stream_from_text_queue(text_queue=text_queue, voice="Sherlock"):
                pass
