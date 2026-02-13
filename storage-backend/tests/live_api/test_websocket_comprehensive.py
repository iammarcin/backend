"""
Comprehensive live API test for WebSocket chat functionality.

Tests multiple WebSocket scenarios using REAL WebSocket connections (not TestClient):
1. Basic chat flow with streaming
2. TTS events coordination

Run with: RUN_MANUAL_TESTS=1 pytest tests/live_api/test_websocket_comprehensive.py -v -s
"""
import asyncio
import json
import os

import pytest
import websockets


@pytest.mark.live_api
@pytest.mark.requires_docker
@pytest.mark.skipif(
    not os.getenv("RUN_MANUAL_TESTS"),
    reason="Live API test - set RUN_MANUAL_TESTS=1 to run"
)
class TestWebSocketComprehensive:
    """Comprehensive WebSocket tests using real connections."""

    @pytest.mark.asyncio
    async def test_basic_chat_flow_with_streaming(
        self,
        auth_token_factory,
    ):
        """
        Test basic WebSocket chat with text streaming.

        Validates:
        - Connection establishment
        - Text streaming events
        - Completion events
        """
        token = auth_token_factory()
        backend_url = os.getenv("BACKEND_WS_URL", "ws://127.0.0.1:8000/chat/ws")
        url = f"{backend_url}?token={token}"

        print(f"\n🔗 Test 1: Basic Chat Flow")
        print(f"   Connecting to: {backend_url}")

        async with websockets.connect(url) as ws:
            print("   ✅ WebSocket connected")

            # Receive websocket_ready
            ready = json.loads(await ws.recv())
            assert ready["type"] == "websocket_ready"
            session_id = ready.get("session_id")
            print(f"   Session ID: {session_id}")

            # Send chat request (canonical snake_case format)
            request = {
                "request_type": "text",
                "user_input": {
                    "prompt": [{"type": "text", "text": "Say hello in 3 words"}],
                    "chat_history": [],
                    "session_id": session_id
                },
                "user_settings": {
                    "text": {
                        "model": "gpt-4o-mini",
                        "temperature": 0.1,
                        "streaming": True
                    }
                },
                "customer_id": 1
            }

            print("   📤 Sending chat request...")
            await ws.send(json.dumps(request))

            # Collect events (dual-flag completion pattern)
            events = []
            text_chunks = []
            event_count = 0
            text_completed = False
            tts_completed = False

            while not (text_completed and tts_completed) and event_count < 50:
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=30.0)
                    event = json.loads(message)
                    event_count += 1
                    event_type = event.get("type")
                    events.append(event_type)

                    if event_type == "text_chunk":
                        text_chunks.append(event.get("content", ""))
                    elif event_type == "text_completed":
                        text_completed = True
                    elif event_type in ("tts_completed", "tts_not_requested"):
                        tts_completed = True

                except asyncio.TimeoutError:
                    print("\n   ⏱️  Timeout waiting for events")
                    break

            # Assertions
            assert "websocket_ready" in events or events[0] == "websocket_ready"
            assert "text_chunk" in events, f"Expected text_chunk events. Got: {events}"
            assert "text_completed" in events, f"Expected text_completed event. Got: {events}"

            full_text = "".join(text_chunks)
            assert len(full_text) > 0, "Expected some text content"

            print(f"   ✅ Received {len(text_chunks)} text chunks")
            print(f"   ✅ Full text: {full_text[:50]}...")
            print(f"   ✅ Events: {' → '.join(events[:10])}")

    @pytest.mark.asyncio
    async def test_websocket_chat_with_tts_events(
        self,
        auth_token_factory,
    ):
        """
        Test WebSocket chat with TTS enabled.

        Validates:
        - TTS event coordination
        - Text + TTS streaming
        - Proper completion ordering
        """
        token = auth_token_factory()
        backend_url = os.getenv("BACKEND_WS_URL", "ws://127.0.0.1:8000/chat/ws")
        url = f"{backend_url}?token={token}"

        print(f"\n🔗 Test 2: Chat with TTS Events")
        print(f"   Connecting to: {backend_url}")

        async with websockets.connect(url) as ws:
            print("   ✅ WebSocket connected")

            ready = json.loads(await ws.recv())
            assert ready["type"] == "websocket_ready"
            session_id = ready.get("session_id")

            # Send chat request with TTS enabled (canonical snake_case format)
            request = {
                "request_type": "text",
                "user_input": {
                    "prompt": [{"type": "text", "text": "Count to three"}],
                    "chat_history": [],
                    "session_id": session_id
                },
                "user_settings": {
                    "text": {
                        "model": "gpt-4o-mini",
                        "temperature": 0.1,
                        "streaming": True
                    },
                    "tts": {
                        "enabled": True,
                        "provider": "openai",
                        "voice": "alloy"
                    }
                },
                "customer_id": 1
            }

            print("   📤 Sending chat request with TTS enabled...")
            await ws.send(json.dumps(request))

            # Collect events (dual-flag completion pattern)
            events = []
            has_text = False
            text_completed = False
            tts_completed = False
            event_count = 0

            while not (text_completed and tts_completed) and event_count < 100:
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=45.0)
                    event = json.loads(message)
                    event_count += 1
                    event_type = event.get("type")
                    events.append(event_type)

                    if event_type == "text_chunk":
                        has_text = True
                    elif event_type == "text_completed":
                        text_completed = True
                    elif event_type in ("tts_completed", "tts_not_requested"):
                        tts_completed = True

                except asyncio.TimeoutError:
                    print("\n   ⏱️  Timeout waiting for TTS events")
                    break

            # Assertions
            assert has_text, f"Expected text_chunk events. Got: {events}"
            assert tts_completed, f"Expected TTS completion event. Got: {events}"
            assert "text_completed" in events, f"Expected text_completed event. Got: {events}"

            # Check event ordering: text_chunk events should come before TTS completion
            if "text_chunk" in events and "tts_completed" in events:
                text_idx = events.index("text_chunk")
                tts_idx = events.index("tts_completed")
                assert text_idx < tts_idx, "text_chunk should come before TTS completion"

            print(f"   ✅ Text events: {has_text}")
            print(f"   ✅ TTS coordination: {tts_completed}")
            print(f"   ✅ Event sequence: {' → '.join(events[:15])}")
