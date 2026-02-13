"""Manual test script for the WebSocket chat endpoint."""

from __future__ import annotations

import asyncio
import json
import os
from urllib.parse import urlencode

import pytest
import websockets


pytestmark = [
    pytest.mark.live_api,
    pytest.mark.skipif(
        os.getenv("RUN_MANUAL_TESTS") != "1",
        reason="Set RUN_MANUAL_TESTS=1 to run manual WebSocket tests",
    ),
]


@pytest.fixture
def anyio_backend() -> str:
    """Limit manual websocket test to the asyncio backend."""

    return "asyncio"


async def _run_websocket_test(token: str | None = None) -> None:
    uri = "ws://127.0.0.1:8000/chat/ws"
    if token:
        uri = f"{uri}?{urlencode({'token': token})}"
    print(f"Connecting to {uri}...")

    try:
        async with websockets.connect(uri) as websocket:
            print("Connected!")

            ready_msg = await websocket.recv()
            print(f"Received: {ready_msg}")

            prompt_text = "Write a haiku about coding"

            # Use canonical snake_case format per WebSocket unification
            message = {
                "request_type": "text",
                "user_input": {
                    "prompt": [{"type": "text", "text": prompt_text}],
                    "chat_history": [],
                },
                "user_settings": {
                    "text": {
                        "model": "gpt-4o-mini",
                        "temperature": 0.7,
                        "streaming": True,
                    }
                },
                "customer_id": 1,
            }

            print(f"\nSending: {json.dumps(message, indent=2)}")
            await websocket.send(json.dumps(message))

            print("\nReceiving response:")
            full_text: list[str] = []

            # Use dual-flag completion pattern
            text_completed = False
            tts_completed = False
            while not (text_completed and tts_completed):
                response = await asyncio.wait_for(websocket.recv(), timeout=60.0)
                data = json.loads(response)

                event_type = data.get("type")
                if event_type == "text_completed":
                    text_completed = True
                    print("\n\nText complete!")
                    continue

                if event_type in ("tts_completed", "tts_not_requested"):
                    tts_completed = True
                    print("TTS complete!")
                    continue

                if event_type == "text_chunk":
                    chunk = data.get("content", "")
                    if chunk:
                        print(chunk, end="", flush=True)
                        full_text.append(chunk)
                    continue

                if event_type == "error":
                    print(f"\nError: {data.get('content')}")
                    break

                print(f"\nReceived event: {event_type}")

            print(f"\n\nFull response:\n{''.join(full_text)}")
    except OSError as exc:
        if "PYTEST_CURRENT_TEST" in os.environ:
            pytest.skip(f"Manual WebSocket test requires server at {uri!r}: {exc}")
        raise RuntimeError(f"Failed to connect to {uri}: {exc}") from exc


@pytest.mark.anyio("asyncio")
async def test_websocket(auth_token_factory) -> None:
    """Connect to the development server and stream a chat response."""

    await _run_websocket_test(auth_token_factory())


if __name__ == "__main__":
    env_token = os.environ.get("CHAT_WS_TOKEN")
    asyncio.run(_run_websocket_test(env_token))
