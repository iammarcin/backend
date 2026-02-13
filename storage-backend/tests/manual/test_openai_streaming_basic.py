"""Manual test for OpenAI streaming provider."""

import asyncio
import os
import sys
from pathlib import Path
from typing import AsyncIterator

import pytest


pytestmark = [
    pytest.mark.live_api,
    pytest.mark.skipif(
        os.getenv("RUN_MANUAL_TESTS") != "1",
        reason="Set RUN_MANUAL_TESTS=1 to run OpenAI streaming manual tests",
    ),
]

# Ensure project root is importable when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.providers.audio.openai_streaming import OpenAIStreamingSpeechProvider
from core.streaming.manager import StreamingManager


async def mock_audio_source() -> AsyncIterator[bytes | None]:
    """Simulate audio chunks from a file for connectivity testing."""

    yield b"\x00\x00" * 1000  # 1000 samples of silence
    yield None  # Signal end of recording


@pytest.mark.asyncio
async def test_basic_connection() -> None:
    """Test OpenAI streaming provider connectivity with mock audio."""

    provider = OpenAIStreamingSpeechProvider()
    provider.configure({"model": "gpt-4o-mini-transcribe"})

    manager = StreamingManager()

    transcription = await provider.transcribe_stream(
        audio_source=mock_audio_source(),
        manager=manager,
        mode="non-realtime",
    )

    # With silence, expect empty transcription
    assert transcription == ""
    print("Basic connection test passed: empty transcription for silence")


if __name__ == "__main__":
    asyncio.run(test_basic_connection())
