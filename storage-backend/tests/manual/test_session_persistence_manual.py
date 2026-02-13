#!/usr/bin/env python3
"""
MANUAL test for session persistence across multiple messages.

This validates that when sending 2 messages in the same WebSocket connection,
they land in the same database session.

Usage:
    export JWT_TOKEN="your-token"
    python tests/manual/test_session_persistence_manual.py
"""

import asyncio
import websockets
import json
import sys
import os


async def run_session_persistence_test():
    """Test that multiple messages share the same session ID.

    NOTE: This is a manual script, NOT a pytest test.
    Run with: python tests/manual/test_session_persistence_manual.py
    """

    # Configuration
    BACKEND_URL = os.getenv("BACKEND_WS_URL", "ws://127.0.0.1:8000/chat/ws")
    JWT_TOKEN = os.getenv("MY_AUTH_BEARER_TOKEN", "")

    if not JWT_TOKEN:
        print("❌ ERROR: JWT_TOKEN environment variable not set")
        print("   Set it with: export JWT_TOKEN='your-token-here'")
        sys.exit(1)

    print(f"🔗 Connecting to: {BACKEND_URL}")

    url = f"{BACKEND_URL}?token={JWT_TOKEN}"

    try:
        async with websockets.connect(url) as ws:
            print("✅ WebSocket connected")

            # Step 1: Receive initial websocket_ready
            ready = json.loads(await ws.recv())
            print(f"📩 Received: {ready['type']}")
            assert ready["type"] == "websocket_ready"

            # === FIRST MESSAGE ===
            print("\n📤 Sending first message...")
            request1 = {
                "request_type": "text",
                "user_input": {
                    "prompt": [{"type": "text", "text": "Hello, this is message 1"}],
                    "chat_history": [],
                    "session_id": ""  # Empty = new session
                },
                "user_settings": {
                    "text": {
                        "model": "gpt-4o-mini",
                        "temperature": 0.3,
                        "streaming": True
                    }
                },
                "customer_id": 1
            }

            await ws.send(json.dumps(request1))

            # Collect events for first message (dual-flag completion pattern)
            first_session_id = None
            text_completed = False
            tts_completed = False
            event_count = 0

            print("📊 Collecting events for first message...")
            while not (text_completed and tts_completed) and event_count < 100:
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=30.0)
                    event = json.loads(message)
                    event_count += 1
                    event_type = event.get("type")

                    print(f"   {event_count}. {event_type}", end="")

                    if event_type == "db_operation_executed":
                        content_str = event.get("content", "")
                        if content_str:
                            content = json.loads(content_str)
                            first_session_id = content.get("session_id")
                            print(f" → session_id: {first_session_id}", end="")

                    elif event_type == "text_completed":
                        text_completed = True

                    elif event_type in ("tts_completed", "tts_not_requested"):
                        tts_completed = True

                    print()

                except asyncio.TimeoutError:
                    print("\n⏱️  Timeout waiting for first message events")
                    break

            if not first_session_id:
                print("\n❌ ERROR: Did not receive session_id from first message")
                return 1

            print(f"\n✓ First message session ID: {first_session_id}")

            # === SECOND MESSAGE ===
            print("\n📤 Sending second message with same session ID...")
            request2 = {
                "request_type": "text",
                "user_input": {
                    "prompt": [{"type": "text", "text": "Hello, this is message 2"}],
                    "chat_history": [],
                    "session_id": first_session_id  # Reuse session
                },
                "user_settings": {
                    "text": {
                        "model": "gpt-4o-mini",
                        "temperature": 0.3,
                        "streaming": True
                    }
                },
                "customer_id": 1
            }

            await ws.send(json.dumps(request2))

            # Collect events for second message (dual-flag completion pattern)
            second_session_id = None
            text_completed = False
            tts_completed = False
            event_count = 0

            print("📊 Collecting events for second message...")
            while not (text_completed and tts_completed) and event_count < 100:
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=30.0)
                    event = json.loads(message)
                    event_count += 1
                    event_type = event.get("type")

                    print(f"   {event_count}. {event_type}", end="")

                    if event_type == "db_operation_executed":
                        content_str = event.get("content", "")
                        if content_str:
                            content = json.loads(content_str)
                            second_session_id = content.get("session_id")
                            print(f" → session_id: {second_session_id}", end="")

                    elif event_type == "text_completed":
                        text_completed = True

                    elif event_type in ("tts_completed", "tts_not_requested"):
                        tts_completed = True

                    print()

                except asyncio.TimeoutError:
                    print("\n⏱️  Timeout waiting for second message events")
                    break

            # === VERIFICATION ===
            print(f"\n" + "=" * 60)
            print("📋 TEST RESULTS")
            print("=" * 60)
            print(f"First message session ID:  {first_session_id}")
            print(f"Second message session ID: {second_session_id}")

            if not second_session_id:
                print("\n❌ ERROR: Did not receive session_id from second message")
                return 1

            if first_session_id == second_session_id:
                print("\n" + "=" * 60)
                print("✅ TEST PASSED")
                print("   Both messages landed in the same session!")
                print("   Session persistence is working correctly.")
                print("=" * 60)
                return 0
            else:
                print("\n" + "=" * 60)
                print("❌ TEST FAILED")
                print("   Messages landed in DIFFERENT sessions!")
                print("   Session persistence is BROKEN.")
                print("=" * 60)
                return 1

    except websockets.exceptions.InvalidStatusCode as e:
        print(f"❌ Connection failed: {e}")
        print("   Check that backend is running and JWT token is valid")
        return 1

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    print("=" * 60)
    print("MANUAL TEST: Session Persistence")
    print("=" * 60)
    print()

    exit_code = asyncio.run(run_session_persistence_test())
    sys.exit(exit_code)
