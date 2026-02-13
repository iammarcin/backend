"""Manual verification tests for Gemini audio streaming and direct mode."""

from __future__ import annotations
import sys

import asyncio
import json
import os
import wave
from pathlib import Path

import httpx
import pytest

BASE_URL = os.getenv("GEMINI_MANUAL_BASE_URL", "http://127.0.0.1:8000/api/v1/chat")


pytestmark = [
    pytest.mark.live_api,
    pytest.mark.skipif(
        os.getenv("RUN_MANUAL_TESTS") != "1",
        reason="Set RUN_MANUAL_TESTS=1 to run Gemini audio manual verification (requires backend, credentials, audio input)",
    ),
]


async def _send_audio_over_websocket(
    *,
    token: str,
    request_type: str,
    speech_settings: dict[str, object],
    audio_bytes: bytes,
) -> list[dict[str, object]]:
    import websockets

    events: list[dict[str, object]] = []
    websocket_base = os.getenv(
        "GEMINI_MANUAL_WEBSOCKET_URL", "ws://127.0.0.1:8000/chat/ws"
    )
    separator = "&" if "?" in websocket_base else "?"
    uri = f"{websocket_base}{separator}token={token}"

    async with websockets.connect(uri) as websocket:
        ready = await websocket.recv()
        events.append(json.loads(ready))

        # Use canonical snake_case format per WebSocket unification
        payload = {
            "request_type": request_type,
            "customer_id": 1,
            "user_input": {
                "prompt": [{"type": "text", "text": "Describe this audio"}],
                "chat_history": [],
            },
            "user_settings": {
                "speech": speech_settings,
                "text": {"model": "gpt-4o-mini", "streaming": True},
                "tts": {"tts_auto_execute": False},
            },
        }
        await websocket.send(json.dumps(payload))

        chunk_size = int(speech_settings.get("recording_sample_rate", 16000)) * 2
        for offset in range(0, len(audio_bytes), chunk_size):
            chunk = audio_bytes[offset: offset + chunk_size]
            if chunk:
                await websocket.send(chunk)
                await asyncio.sleep(0.05)

        await websocket.send(json.dumps({"type": "RecordingFinished"}))

        # Use dual-flag completion pattern
        text_completed = False
        tts_completed = False
        while not (text_completed and tts_completed):
            message = await asyncio.wait_for(websocket.recv(), timeout=60.0)
            if isinstance(message, bytes):
                continue
            data = json.loads(message)
            events.append(data)
            event_type = data.get("type")
            if event_type == "text_completed":
                text_completed = True
            elif event_type in ("tts_completed", "tts_not_requested"):
                tts_completed = True

    return events


@pytest.mark.anyio
async def test_gemini_streaming_stt(audio_path: Path, token: str) -> bool:
    print("\n" + "=" * 60)
    print("TEST 1: Gemini Streaming STT")
    print("=" * 60)

    with wave.open(str(audio_path), "rb") as wf:
        sample_rate = wf.getframerate()
        audio_bytes = wf.readframes(wf.getnframes())

    events = await _send_audio_over_websocket(
        token=token,
        request_type="audio",
        speech_settings={
            "model": "gemini-2.5-flash",
            "recording_sample_rate": sample_rate,
        },
        audio_bytes=audio_bytes,
    )

    transcriptions = [
        event.get("content")
        for event in events
        if event.get("type") == "transcription"
    ]
    responses = [
        event.get("content")
        for event in events
        if event.get("type") == "text_chunk"
    ]

    if not transcriptions:
        print("❌ No transcription received")
        return False
    if not responses:
        print("❌ No text_chunk response events received")
        return False

    print("✓ Received transcription and text_chunk response events")
    return True


@pytest.mark.anyio
async def test_audio_direct_mode(audio_path: Path, token: str) -> bool:
    print("\n" + "=" * 60)
    print("TEST 2: Audio Direct Mode")
    print("=" * 60)

    with wave.open(str(audio_path), "rb") as wf:
        sample_rate = wf.getframerate()
        audio_bytes = wf.readframes(wf.getnframes())

    events = await _send_audio_over_websocket(
        token=token,
        request_type="audio",
        speech_settings={
            "model": "gemini-2.5-flash",
            "recording_sample_rate": sample_rate,
            "send_full_audio_to_llm": True,
        },
        audio_bytes=audio_bytes,
    )

    text_chunks = [
        event.get("content")
        for event in events
        if event.get("type") == "text_chunk"
    ]

    if not text_chunks:
        print("❌ No multimodal response received")
        return False

    print("✓ Audio direct mode returned text_chunk response")
    return True


async def test_database_persistence(token: str) -> bool:
    print("\n" + "=" * 60)
    print("TEST 3: Database Persistence")
    print("=" * 60)

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/api/v1/chat/conversations?limit=1",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        if response.status_code != 200:
            print(f"❌ Failed to fetch conversations: {response.status_code}")
            return False
        conversations = response.json()
        print(f"✓ Retrieved {len(conversations)} conversation(s)")
        return True


async def test_error_scenarios(token: str) -> bool:
    print("\n" + "=" * 60)
    print("TEST 4: Error Scenarios")
    print("=" * 60)

    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                f"{BASE_URL}/api/v1/audio/transcribe-stream",
                json={},
                timeout=10,
            )
        except httpx.HTTPStatusError as exc:
            print(f"✓ Empty payload rejected ({exc.response.status_code})")
        except Exception as exc:  # pragma: no cover - manual runner only
            print(f"❌ Unexpected error during error scenario test: {exc}")
            return False

    return True


async def main(audio_file: Path, token: str) -> int:
    print("\n" + "=" * 70)
    print(" GEMINI AUDIO FEATURES - MANUAL TEST SUITE")
    print("=" * 70)

    results = {
        "gemini_streaming_stt": await test_gemini_streaming_stt(audio_file, token),
        "audio_direct_mode": await test_audio_direct_mode(audio_file, token),
        "database_persistence": await test_database_persistence(token),
        "error_scenarios": await test_error_scenarios(token),
    }

    print("\n" + "=" * 70)
    print(" TEST SUMMARY")
    print("=" * 70)
    for name, passed in results.items():
        status = "✓ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")

    passed = sum(1 for value in results.values() if value)
    total = len(results)
    print("-" * 70)
    print(f"TOTAL: {passed}/{total} tests passed")
    print("=" * 70)

    return 0 if passed == total else 1


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python tests/manual/test_gemini_audio_complete.py <audio_file.wav> <MY_AUTH_BEARER_TOKEN>")
        sys.exit(1)

    audio_path = Path(sys.argv[1])
    if not audio_path.exists():
        print(f"Audio file not found: {audio_path}")
        sys.exit(1)

    token = sys.argv[2]
    exit_code = asyncio.run(main(audio_path, token))
    sys.exit(exit_code)
