import base64
import time
from threading import Event
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from main import app

import features.tts.websocket as tts_ws


class StubRealtimeClient(tts_ws.ElevenLabsRealtimeClient):
    """Stub realtime client that echoes text as base64 audio."""

    def __init__(self, settings: tts_ws.ElevenLabsRealtimeSettings) -> None:  # type: ignore[call-arg]
        # Bypass parent initialisation; the stub does not require API keys.
        self.settings = settings
        self.received: List[str] = []
        self.finished = Event()

    async def run(  # type: ignore[override]
        self,
        text_queue: "asyncio.Queue[str | None]",  # type: ignore[name-defined]
        audio_queue: "asyncio.Queue[Dict[str, Any] | None]",
        timings: Dict[str, float],
        stop_event: "asyncio.Event",  # type: ignore[name-defined]
    ) -> None:
        import asyncio

        timings["tts_request_sent_time"] = time.time()
        try:
            while True:
                text = await text_queue.get()
                if text is None or stop_event.is_set():
                    break
                self.received.append(text)
                encoded = base64.b64encode(text.encode()).decode()
                if "tts_first_response_time" not in timings:
                    timings["tts_first_response_time"] = time.time()
                await audio_queue.put({"type": "audio", "chunk": encoded})
        finally:
            timings["tts_completed_time"] = time.time()
            await audio_queue.put({"type": "status", "status": "finished"})
            await audio_queue.put(None)
            self.finished.set()


class DisconnectAwareClient(tts_ws.ElevenLabsRealtimeClient):
    """Stub client that records when it is stopped."""

    def __init__(self, settings: tts_ws.ElevenLabsRealtimeSettings) -> None:  # type: ignore[call-arg]
        self.stopped = Event()

    async def run(  # type: ignore[override]
        self,
        text_queue: "asyncio.Queue[str | None]",  # type: ignore[name-defined]
        audio_queue: "asyncio.Queue[Dict[str, Any] | None]",
        timings: Dict[str, float],
        stop_event: "asyncio.Event",  # type: ignore[name-defined]
    ) -> None:
        import asyncio

        try:
            while True:
                text = await text_queue.get()
                if text is None or stop_event.is_set():
                    break
                await asyncio.sleep(0)
        finally:
            await audio_queue.put(None)
            self.stopped.set()


@pytest.fixture(autouse=True)
def restore_realtime_client():
    original = tts_ws.ElevenLabsRealtimeClient
    yield
    tts_ws.ElevenLabsRealtimeClient = original


def test_tts_websocket_streams_audio(monkeypatch, auth_token: str):
    created_clients: List[StubRealtimeClient] = []

    def factory(settings: tts_ws.ElevenLabsRealtimeSettings) -> StubRealtimeClient:
        client = StubRealtimeClient(settings)
        created_clients.append(client)
        return client

    tts_ws.ElevenLabsRealtimeClient = factory  # type: ignore[assignment]

    test_client = TestClient(app)

    with test_client.websocket_connect(
        "/tts/ws", headers={"Authorization": f"Bearer {auth_token}"}
    ) as websocket:
        ready = websocket.receive_json()
        assert ready["type"] == "websocket_ready"

        websocket.send_json(
            {
                "type": "init",
                "payload": {
                    "customer_id": 7,
                    "session_id": "abc123",
                    "user_settings": {
                        "tts": {
                            "voice": "custom_voice",
                            "chunkSchedule": [10, 20, 30, 40],
                        }
                    },
                    "text": "hello world",
                },
            }
        )

        init_status = websocket.receive_json()
        assert init_status["type"] == "status"
        assert init_status["status"] == "initialised"

        websocket.send_json({"type": "send_text", "text": "second"})
        websocket.send_json({"type": "stop"})

        messages: List[Dict[str, Any]] = []
        try:
            while True:
                messages.append(websocket.receive_json())
        except WebSocketDisconnect:
            pass

    assert created_clients, "Expected realtime client to be constructed"
    received_chunks = [msg for msg in messages if msg.get("type") == "audio_chunk"]
    assert len(received_chunks) >= 2

    payload_texts = {
        base64.b64decode(chunk["chunk"]).decode() for chunk in received_chunks
    }
    assert payload_texts >= {"hello world", "second"}

    final_status = next(msg for msg in messages if msg.get("status") == "completed")
    timings = final_status.get("timings", {})
    assert "tts_request_sent_time" in timings
    assert "tts_completed_time" in timings

    assert created_clients[0].received == ["hello world", "second"]
    assert created_clients[0].finished.wait(timeout=1), "Expected client to finish"


def test_tts_websocket_disconnect_triggers_stop(monkeypatch, auth_token: str):
    stub_client = DisconnectAwareClient(tts_ws.ElevenLabsRealtimeSettings(
        model="stub", voice="voice", audio_format="mp3", chunk_schedule=[1, 2, 3, 4],
        stability=0.1, similarity_boost=0.1, style=0.0, speaker_boost=False, inactivity_timeout=1,
    ))

    def factory(settings: tts_ws.ElevenLabsRealtimeSettings) -> DisconnectAwareClient:
        return stub_client

    tts_ws.ElevenLabsRealtimeClient = factory  # type: ignore[assignment]

    test_client = TestClient(app)

    with test_client.websocket_connect(
        "/tts/ws", headers={"Authorization": f"Bearer {auth_token}"}
    ) as websocket:
        websocket.receive_json()
        websocket.send_json({"type": "init", "payload": {"user_settings": {}}})
        websocket.receive_json()

    assert stub_client.stopped.wait(timeout=1), "Realtime client did not stop after disconnect"
