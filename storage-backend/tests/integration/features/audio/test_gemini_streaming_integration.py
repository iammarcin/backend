"""Integration tests for Gemini streaming provider selection and workflow."""

import asyncio
from unittest.mock import patch

import pytest

from core.providers.audio.factory import get_audio_provider
from core.streaming.manager import StreamingManager


@pytest.mark.anyio
async def test_factory_returns_gemini_streaming_for_gemini_model() -> None:
    """Factory routes Gemini models to streaming provider."""

    settings = {
        "audio": {
            "model": "gemini-2.5-flash",
            "language": "en",
        }
    }

    provider = get_audio_provider(settings, action="stream")

    assert provider.name == "gemini-streaming"
    assert provider.streaming_capable is True
    assert provider.model == "gemini-2.5-flash"


@pytest.mark.anyio
async def test_factory_returns_deepgram_for_non_gemini_streaming() -> None:
    """Factory uses Deepgram for non-Gemini streaming requests."""

    settings = {
        "audio": {
            "model": "nova-3",
        }
    }

    provider = get_audio_provider(settings, action="stream")

    assert provider.name == "deepgram"
    assert provider.streaming_capable is True


@pytest.mark.anyio
async def test_end_to_end_transcription_flow() -> None:
    """Complete flow from audio source to transcription result."""

    settings = {
        "audio": {
            "model": "gemini-2.5-flash",
            "language": "en",
        }
    }

    provider = get_audio_provider(settings, action="stream")
    manager = StreamingManager()
    output_queue: asyncio.Queue = asyncio.Queue()
    manager.add_queue(output_queue)

    with patch(
        "core.providers.audio.gemini_streaming.get_gemini_client"
    ) as mock_client_factory:
        mock_client = mock_client_factory.return_value
        mock_response = type("Response", (), {"text": "Hello world"})()
        mock_client.models.generate_content.return_value = mock_response

        async def audio_source():
            chunk_size = 24000 * 2 * 3
            yield b"\x00" * chunk_size
            yield None

        result = await provider.transcribe_stream(
            audio_source=audio_source(),
            manager=manager,
            mode="non-realtime",
        )

        assert result == "Hello world"
        assert mock_client.models.generate_content.called

        messages = []
        while not output_queue.empty():
            messages.append(await output_queue.get())

        transcription_events = [
            message
            for message in messages
            if message.get("type") == "transcription"
        ]
        assert len(transcription_events) > 0

