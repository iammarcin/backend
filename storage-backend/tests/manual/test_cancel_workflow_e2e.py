"""Manual E2E test for verifying WebSocket workflow cancellation.

Usage:
    1. Ensure the backend server is running locally on http://127.0.0.1:8000
    2. Set MY_AUTH_BEARER_TOKEN environment variable with a valid JWT token
    3. Set RUN_MANUAL_TESTS=1 to enable manual tests
    4. Run: pytest tests/manual/test_cancel_workflow_e2e.py -v
    5. Or run directly: python tests/manual/test_cancel_workflow_e2e.py
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import pytest
import websockets


DEFAULT_URI = os.getenv("TEST_WS_URI", "ws://127.0.0.1:8000/chat/ws")
MANUAL_TESTS_ENABLED = os.getenv("RUN_MANUAL_TESTS") == "1"


def _require_manual_environment() -> None:
    if not MANUAL_TESTS_ENABLED:
        pytest.skip("Manual websocket tests require RUN_MANUAL_TESTS=1")


TOKEN = os.environ.get("MY_AUTH_BEARER_TOKEN")


@pytest.mark.live_api
@pytest.mark.skipif(
    os.getenv("RUN_MANUAL_TESTS") != "1",
    reason="Live API test - set RUN_MANUAL_TESTS=1 to run",
)
async def test_cancel_text_workflow() -> None:
    """Connect to the websocket endpoint, start a workflow, then cancel it."""
    _require_manual_environment()

    if not TOKEN:
        pytest.skip("MY_AUTH_BEARER_TOKEN not set for manual websocket tests")

    uri = f"{DEFAULT_URI}?token={TOKEN}"

    async with websockets.connect(uri) as websocket:
        ready = await websocket.recv()
        print(f"Ready event: {ready}")

        request_payload: dict[str, Any] = {
            "type": "text",
            "request_type": "text",
            "prompt": "Write an exhaustive history of computing in 20,000 words.",
            "settings": {
                "text": {"model": "gpt-4o", "temperature": 0.7, "max_tokens": 4000},
                "tts": {"tts_auto_execute": False},
            },
        }
        await websocket.send(json.dumps(request_payload))

        # Allow the workflow to stream a few chunks
        for _ in range(5):
            chunk = await websocket.recv()
            print(f"Chunk: {chunk[:120]}...")

        print("\n🛑 Sending cancel request\n")
        await websocket.send(json.dumps({"type": "cancel"}))

        # Dual-flag completion pattern: wait for both text_completed and tts_not_requested/tts_completed
        text_completed = False
        tts_completed = False
        cancelled_received = False
        timeout_seconds = 10

        try:
            while not (text_completed and tts_completed):
                message = await asyncio.wait_for(websocket.recv(), timeout=timeout_seconds)
                event = json.loads(message)
                event_type = event.get("type")
                print(f"Event after cancel: {event_type}")

                if event_type == "cancelled":
                    cancelled_received = True
                    print("✅ Backend acknowledged cancellation.")
                elif event_type == "text_completed":
                    text_completed = True
                    print("✅ Text completed.")
                elif event_type in ("tts_completed", "tts_not_requested"):
                    tts_completed = True
                    print(f"✅ TTS completed ({event_type}).")

            assert cancelled_received, "Expected 'cancelled' event but didn't receive it"
            print("\n✅ Workflow cancelled successfully with dual-flag completion.")

        except asyncio.TimeoutError:
            pytest.fail(f"Timeout after {timeout_seconds}s waiting for completion events")


if __name__ == "__main__":
    asyncio.run(test_cancel_text_workflow())
