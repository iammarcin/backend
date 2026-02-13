"""Integration tests for the realtime chat service wiring."""

from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import Iterable, Mapping

import pytest

from core.providers.realtime.base import BaseRealtimeProvider, RealtimeEvent, RealtimeEventType
from core.streaming.manager import StreamingManager
from features.realtime.schemas import RealtimeSessionSettings
from features.realtime.service import RealtimeChatService
from fastapi.websockets import WebSocketDisconnect


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class StubWebSocket:
    """Minimal websocket implementation used to exercise the service."""

    def __init__(self, messages: Iterable[object]) -> None:
        self._messages = list(messages)
        self.sent: list[Mapping[str, object]] = []
        self.sent_text: list[str] = []
        self.accepted = False
        self.closed = False
        self.query_params = {"customer_id": "42"}
        self.headers: Mapping[str, str] = {}

    async def accept(self) -> None:
        self.accepted = True

    async def receive(self) -> Mapping[str, object]:
        while not self._messages:
            if self.closed:
                raise WebSocketDisconnect(code=getattr(self, "close_code", 1000))
            await asyncio.sleep(0)

        await asyncio.sleep(0)
        message = self._messages.pop(0)
        if callable(message):
            message = message()
        if asyncio.iscoroutine(message):
            message = await message
        if isinstance(message, Exception):
            raise message
        if isinstance(message, Mapping):
            return dict(message)
        if isinstance(message, (bytes, bytearray, memoryview)):
            return {
                "type": "websocket.receive",
                "bytes": bytes(message)
                if not isinstance(message, memoryview)
                else message.tobytes(),
                "text": None,
            }
        return {"type": "websocket.receive", "text": str(message)}

    async def receive_text(self) -> str:
        payload = await self.receive()
        text = payload.get("text")
        if text is None:
            raise RuntimeError("receive_text called for non-text payload")
        return str(text)

    async def send_json(self, payload: Mapping[str, object]) -> None:
        self.sent.append(dict(payload))

    async def send_text(self, data: str) -> None:
        self.sent_text.append(data)
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError:
            parsed = {"type": "text_chunk", "content": data}
        if isinstance(parsed, Mapping):
            self.sent.append(dict(parsed))
        else:  # pragma: no cover - defensive guard
            self.sent.append({"type": "text_chunk", "content": data})

    async def close(
        self, code: int = 1000, reason: str | None = None
    ) -> None:  # pragma: no cover - defensive
        self.closed = True
        self.close_code = code
        self.close_reason = reason


class StubProvider(BaseRealtimeProvider):
    def __init__(self, events: Iterable[RealtimeEvent]) -> None:
        self.events = list(events)
        self.opened_with: Mapping[str, object] | None = None
        self.sent_payloads: list[Mapping[str, object]] = []
        self.session_closed = False

    async def open_session(self, *, settings: Mapping[str, object]) -> None:
        self.opened_with = dict(settings)

    async def close_session(self) -> None:
        self.session_closed = True

    async def send_user_event(self, payload: Mapping[str, object]) -> None:
        self.sent_payloads.append(dict(payload))

    async def receive_events(self):  # type: ignore[override]
        for event in self.events:
            yield event


class AudioCapturingProvider(BaseRealtimeProvider):
    def __init__(self) -> None:
        self.session_opened = False
        self.session_closed = False
        self.audio_queue: asyncio.Queue[bytes | None] | None = None
        self.sent_payloads: list[Mapping[str, object]] = []

    async def open_session(self, *, settings: Mapping[str, object]) -> None:
        self.session_opened = True

    async def close_session(self) -> None:
        self.session_closed = True

    async def send_user_event(self, payload: Mapping[str, object]) -> None:
        self.sent_payloads.append(dict(payload))

    async def set_input_audio_queue(self, queue: asyncio.Queue[bytes | None]) -> None:
        await super().set_input_audio_queue(queue)
        self.audio_queue = queue

    async def receive_events(self):  # type: ignore[override]
        if False:
            yield RealtimeEvent(RealtimeEventType.CONTROL, {})
        return


class StubStorageService:
    def __init__(self) -> None:
        self.uploads: list[Mapping[str, object]] = []

    async def upload_audio(self, **kwargs) -> str:
        self.uploads.append(kwargs)
        return "https://example.com/audio"


class StubChatHistoryService:
    def __init__(self) -> None:
        self.requests: list = []

    async def create_message(self, request):
        self.requests.append(request)

        class _Messages:
            session_id = "session-1"
            user_message_id = 101
            ai_message_id = 202

        class _Result:
            messages = _Messages()

        return _Result()


async def test_realtime_service_streams_and_persists_turn() -> None:
    audio_chunk = base64.b64encode(b"sample").decode()
    events = [
        RealtimeEvent(RealtimeEventType.MESSAGE, {"event": "user.transcript.completed", "text": "Hi"}),
        RealtimeEvent(
            RealtimeEventType.MESSAGE,
            {"event": "assistant.text.delta", "response_id": "resp-1", "text": "Hello"},
        ),
        RealtimeEvent(
            RealtimeEventType.AUDIO_CHUNK,
            {"response_id": "resp-1", "audio": audio_chunk},
        ),
        RealtimeEvent(
            RealtimeEventType.AUDIO_CHUNK,
            {"event": "assistant.audio.completed", "response_id": "resp-1"},
        ),
        RealtimeEvent(
            RealtimeEventType.CONTROL,
            {"event": "turn.completed", "response_id": "resp-1", "status": "completed"},
        ),
    ]

    provider = StubProvider(events)
    storage = StubStorageService()
    chat_history = StubChatHistoryService()

    service = RealtimeChatService(
        manager_factory=StreamingManager,
        chat_history_service=chat_history,
        storage_service_factory=lambda: storage,
        provider_resolver=lambda model: provider,
        session_defaults=RealtimeSessionSettings(tts_auto_execute=True),
    )

    websocket = StubWebSocket(
        [
            json.dumps({"type": "input.message", "content": "hello"}),
            json.dumps({"type": "realtime.close"}),
        ]
    )

    await service.handle_websocket(websocket)

    # Handshake + ack + streamed events + persistence notification
    assert websocket.sent[0]["type"] == "websocket_ready"
    assert any(payload.get("type") == "realtime.ack" for payload in websocket.sent)
    ai_control_events = [
        payload
        for payload in websocket.sent
        if payload.get("type") == "control"
        and isinstance(payload.get("payload"), Mapping)
        and payload["payload"].get("event") == "turn.ai_responding"
    ]
    assert ai_control_events, "Expected ai responding control event before assistant output"
    first_stream_index = next(
        idx
        for idx, payload in enumerate(websocket.sent)
        if payload.get("type") in {"text_chunk", "audio"}
    )
    ai_control_index = next(
        idx
        for idx, payload in enumerate(websocket.sent)
        if payload.get("type") == "control"
        and isinstance(payload.get("payload"), Mapping)
        and payload["payload"].get("event") == "turn.ai_responding"
    )
    assert ai_control_index < first_stream_index
    ai_control_payload = ai_control_events[0]["payload"]
    assert ai_control_payload.get("turn_number") == 0
    assert ai_control_payload.get("response_id") == "resp-1"
    assert any(payload.get("type") == "turn.persisted" for payload in websocket.sent)

    assert provider.opened_with is not None
    assert provider.sent_payloads[0]["type"] == "input.message"
    assert storage.uploads, "expected audio upload payload"
    stored_audio = storage.uploads[0]["audio_bytes"]
    assert stored_audio.startswith(b"RIFF"), "audio bytes should be WAV encoded"
    assert stored_audio.endswith(b"sample"), "audio payload should include streamed chunk"
    assert chat_history.requests[0].user_message.message == "Hi"
    assert chat_history.requests[0].ai_response.file_names == ["https://example.com/audio"]


async def test_realtime_service_test_mode_bypasses_provider() -> None:
    provider = StubProvider([])
    storage = StubStorageService()
    chat_history = StubChatHistoryService()

    service = RealtimeChatService(
        manager_factory=StreamingManager,
        chat_history_service=chat_history,
        storage_service_factory=lambda: storage,
        provider_resolver=lambda model: provider,
        session_defaults=RealtimeSessionSettings(return_test_data=True),
    )

    websocket = StubWebSocket(
        [
            json.dumps({"type": "input.message"}),
            json.dumps({"type": "realtime.close"}),
        ]
    )

    await service.handle_websocket(websocket)

    assert provider.opened_with is None
    assert chat_history.requests, "test mode should still persist a turn"
    assert any(payload.get("type") == "turn.persisted" for payload in websocket.sent)


async def test_realtime_service_routes_binary_audio_into_queue() -> None:
    provider = AudioCapturingProvider()
    storage = StubStorageService()
    chat_history = StubChatHistoryService()

    service = RealtimeChatService(
        manager_factory=StreamingManager,
        chat_history_service=chat_history,
        storage_service_factory=lambda: storage,
        provider_resolver=lambda model: provider,
        session_defaults=RealtimeSessionSettings(),
    )

    audio_chunk = b"\x00\x01\x02"
    websocket = StubWebSocket(
        [
            {"type": "websocket.receive", "bytes": audio_chunk, "text": None},
            json.dumps({"type": "RecordingFinished"}),
            json.dumps({"type": "realtime.close"}),
        ]
    )

    await service.handle_websocket(websocket)

    assert provider.audio_queue is not None
    drained: list[bytes | None] = []
    while True:
        try:
            drained.append(provider.audio_queue.get_nowait())
        except asyncio.QueueEmpty:
            break

    assert audio_chunk in drained
    assert drained[-1] is None


async def test_tts_auto_execute_toggles_modalities_and_provider_output() -> None:
    async def _run_turn(
        *, settings: RealtimeSessionSettings, events: list[RealtimeEvent]
    ) -> tuple[StubProvider, StubChatHistoryService, StubStorageService]:
        provider = StubProvider(events)
        storage = StubStorageService()
        chat_history = StubChatHistoryService()

        service = RealtimeChatService(
            manager_factory=StreamingManager,
            chat_history_service=chat_history,
            storage_service_factory=lambda: storage,
            provider_resolver=lambda model: provider,
            session_defaults=settings,
        )

        websocket = StubWebSocket(
            [
                json.dumps({"type": "input.message", "content": "hello"}),
                json.dumps({"type": "realtime.close"}),
            ]
        )

        await service.handle_websocket(websocket)
        return provider, chat_history, storage

    text_events = [
        RealtimeEvent(
            RealtimeEventType.MESSAGE,
            {"event": "user.transcript.completed", "text": "Hi there"},
        ),
        RealtimeEvent(
            RealtimeEventType.MESSAGE,
            {"event": "assistant.text.delta", "response_id": "resp-1", "text": "Hello"},
        ),
        RealtimeEvent(
            RealtimeEventType.MESSAGE,
            {"event": "assistant.text.completed", "response_id": "resp-1"},
        ),
        RealtimeEvent(
            RealtimeEventType.CONTROL,
            {"event": "turn.completed", "response_id": "resp-1", "status": "completed"},
        ),
    ]

    provider_text, chat_history_text, storage_text = await _run_turn(
        settings=RealtimeSessionSettings(enable_audio_output=True, tts_auto_execute=False),
        events=text_events,
    )

    assert provider_text.opened_with is not None
    assert provider_text.opened_with.get("enable_audio_output") is False
    assert chat_history_text.requests
    text_modalities = chat_history_text.requests[0].user_message.api_text_gen_settings["modalities"]
    assert text_modalities == ["text"]
    response_modalities = chat_history_text.requests[0].ai_response.api_text_gen_settings["modalities"]
    assert response_modalities == ["text"]
    assert not storage_text.uploads, "audio should not be uploaded when TTS auto execute is disabled"

    audio_chunk = base64.b64encode(b"audio").decode()
    audio_events = [
        RealtimeEvent(
            RealtimeEventType.MESSAGE,
            {"event": "user.transcript.completed", "text": "Hi again"},
        ),
        RealtimeEvent(
            RealtimeEventType.MESSAGE,
            {"event": "assistant.text.delta", "response_id": "resp-2", "text": "Reply"},
        ),
        RealtimeEvent(
            RealtimeEventType.AUDIO_CHUNK,
            {"response_id": "resp-2", "audio": audio_chunk},
        ),
        RealtimeEvent(
            RealtimeEventType.AUDIO_CHUNK,
            {"event": "assistant.audio.completed", "response_id": "resp-2"},
        ),
        RealtimeEvent(
            RealtimeEventType.CONTROL,
            {"event": "turn.completed", "response_id": "resp-2", "status": "completed"},
        ),
    ]

    provider_audio, chat_history_audio, storage_audio = await _run_turn(
        settings=RealtimeSessionSettings(enable_audio_output=True, tts_auto_execute=True),
        events=audio_events,
    )

    assert provider_audio.opened_with is not None
    assert provider_audio.opened_with.get("enable_audio_output") is True
    assert chat_history_audio.requests
    audio_modalities = chat_history_audio.requests[0].user_message.api_text_gen_settings["modalities"]
    assert audio_modalities == ["audio"]
    response_modalities_audio = chat_history_audio.requests[0].ai_response.api_text_gen_settings["modalities"]
    assert response_modalities_audio == ["audio"]
    assert storage_audio.uploads, "audio should be uploaded when TTS auto execute is enabled"


async def test_single_shot_recording_streams_response_before_close() -> None:
    events = [
        RealtimeEvent(
            RealtimeEventType.MESSAGE,
            {
                "event": "assistant.text.delta",
                "text": "Here is the answer",
                "response_id": "resp-123",
            },
        ),
        RealtimeEvent(
            RealtimeEventType.MESSAGE,
            {"event": "assistant.text.completed", "response_id": "resp-123"},
        ),
        RealtimeEvent(
            RealtimeEventType.CONTROL,
            {"event": "turn.completed", "response_id": "resp-123", "status": "completed"},
        ),
    ]

    provider = StubProvider(events)
    storage = StubStorageService()
    chat_history = StubChatHistoryService()

    service = RealtimeChatService(
        manager_factory=StreamingManager,
        chat_history_service=chat_history,
        storage_service_factory=lambda: storage,
        provider_resolver=lambda model: provider,
        session_defaults=RealtimeSessionSettings(vad_enabled=False),
    )

    audio_chunk = b"\x00\x01\x02"

    async def _delayed_disconnect() -> Mapping[str, object]:
        await asyncio.sleep(0.05)
        return {"type": "websocket.disconnect"}

    websocket = StubWebSocket(
        [
            {"type": "websocket.receive", "bytes": audio_chunk, "text": None},
            json.dumps({"type": "RecordingFinished"}),
            _delayed_disconnect(),
        ]
    )

    await service.handle_websocket(websocket)

    text_indices = [
        idx
        for idx, payload in enumerate(websocket.sent)
        if payload.get("type") == "text_chunk" and payload.get("content") == "Here is the answer"
    ]
    assert text_indices, "assistant response should be forwarded to the client"

    closed_index = next(
        idx
        for idx, payload in enumerate(websocket.sent)
        if payload.get("type") == "session.closed"
    )
    assert text_indices[0] < closed_index, "session should close after streaming the assistant response"
