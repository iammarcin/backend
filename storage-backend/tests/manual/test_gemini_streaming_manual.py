"""Manual test script for Gemini streaming provider.

This script requires:
1. Backend server running (python main.py)
2. GOOGLE_API_KEY environment variable set
3. Real audio file for testing

Usage:
    python tests/manual/test_gemini_streaming_manual.py <audio_file.wav>
"""

import asyncio
import os
import sys
import wave

import pytest

from core.providers.audio.factory import get_audio_provider
from core.streaming.manager import StreamingManager


pytestmark = [
    pytest.mark.live_api,
    pytest.mark.skipif(
        os.getenv("RUN_MANUAL_TESTS") != "1",
        reason="Set RUN_MANUAL_TESTS=1 to run Gemini streaming manual tests (requires backend, credentials, audio sample)",
    ),
]


async def test_with_real_audio_file(audio_file_path: str) -> None:
    """Test transcription with a real audio file."""

    print(f"Testing Gemini streaming with: {audio_file_path}")

    with wave.open(audio_file_path, "rb") as wf:
        sample_rate = wf.getframerate()
        channels = wf.getnchannels()
        audio_data = wf.readframes(wf.getnframes())

    print(f"Audio info: {sample_rate}Hz, {channels} channels, {len(audio_data)} bytes")

    settings = {
        "audio": {
            "model": "gemini-2.5-flash",
            "language": "en",
            "recording_sample_rate": sample_rate,
            "sample_rate": 16000,
            "channels": channels,
        }
    }

    provider = get_audio_provider(settings, action="stream")
    manager = StreamingManager()
    output_queue: asyncio.Queue = asyncio.Queue()
    manager.add_queue(output_queue)

    async def audio_source():
        chunk_size = sample_rate * 2 * 1
        offset = 0
        while offset < len(audio_data):
            chunk = audio_data[offset : offset + chunk_size]
            if chunk:
                yield chunk
                print(f"Sent chunk: {len(chunk)} bytes")
                await asyncio.sleep(0.1)
            offset += chunk_size
        yield None

    print("\nStarting transcription...")
    result = await provider.transcribe_stream(
        audio_source=audio_source(),
        manager=manager,
        mode="non-realtime",
    )

    print("\n=== FINAL TRANSCRIPTION ===")
    print(result)
    print("===========================\n")

    print("Streaming events:")
    while not output_queue.empty():
        event = await output_queue.get()
        print(f"  {event}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tests/manual/test_gemini_streaming_manual.py <audio_file.wav>")
        print("\nExample:")
        print("  python tests/manual/test_gemini_streaming_manual.py /tmp/recording.wav")
        sys.exit(1)

    audio_file = sys.argv[1]
    asyncio.run(test_with_real_audio_file(audio_file))
