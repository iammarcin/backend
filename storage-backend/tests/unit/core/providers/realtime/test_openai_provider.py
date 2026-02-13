"""Unit tests for the OpenAI realtime provider implementation."""

from __future__ import annotations

import asyncio
import base64
import json
from typing import Iterable, Mapping

import pytest
from websockets.exceptions import ConnectionClosedOK

from core.providers.realtime.base import RealtimeEventType
from core.providers.realtime.openai import OpenAIRealtimeProvider


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class DummyConnection:
    """Lightweight websocket stub used by the provider unit tests."""

    def __init__(self, messages: Iterable[str] | None = None) -> None:
        self._messages = list(messages or [])
        self.sent: list[str | bytes] = []
        self.closed = False

    async def send(self, data: str | bytes) -> None:
        self.sent.append(data)

    async def recv(self) -> str:
        if not self._messages:
            raise ConnectionClosedOK(None, None)
        return self._messages.pop(0)

    async def close(self) -> None:
        self.closed = True


def _connect_factory(messages: Iterable[str] | None = None):
    async def _connect(url: str, **_: Mapping[str, object]) -> DummyConnection:
        return DummyConnection(messages)

    return _connect


async def test_open_session_sends_session_update_event() -> None:
    provider = OpenAIRealtimeProvider(api_key="key", connect=_connect_factory())

    await provider.open_session(
        settings={
            "model": "gpt-realtime",
            "voice": "alloy",
            "temperature": 0.6,
            "vad_enabled": True,
            "enable_audio_input": True,
            "enable_audio_output": True,
            "tts_auto_execute": True,
        }
    )

    assert provider._client is not None  # noqa: SLF001 - accessed for assertions
    assert provider._client.sent, "session.update event should be sent on open"
    payload = json.loads(provider._client.sent[0])
    assert payload["type"] == "session.update"
    session_payload = payload["session"]
    assert session_payload["type"] == "realtime"
    assert session_payload["model"] == "gpt-realtime"
    assert session_payload["output_modalities"] == ["audio"]
    audio_config = session_payload["audio"]
    assert audio_config["output"]["voice"] == "alloy"
    turn_detection = audio_config["input"]["turn_detection"]
    assert turn_detection["type"] == "server_vad"
    assert "translate" not in audio_config["input"]["transcription"]


async def test_open_session_ignores_translation_settings_for_now() -> None:
    provider = OpenAIRealtimeProvider(api_key="key", connect=_connect_factory())

    await provider.open_session(
        settings={
            "model": "gpt-realtime",
            "voice": "alloy",
            "temperature": 0.6,
            "vad_enabled": True,
            "enable_audio_input": True,
            "enable_audio_output": True,
            "tts_auto_execute": True,
            "live_translation": True,
            "translation_language": "es",
        }
    )

    assert provider._client is not None  # noqa: SLF001 - accessed for assertions
    payload = json.loads(provider._client.sent[0])
    transcription = payload["session"]["audio"]["input"]["transcription"]
    assert "translate" not in transcription
    assert "target_language" not in transcription


async def test_open_session_disables_turn_detection_when_vad_disabled() -> None:
    provider = OpenAIRealtimeProvider(api_key="key", connect=_connect_factory())

    await provider.open_session(
        settings={
            "model": "gpt-realtime",
            "vad_enabled": False,
            "enable_audio_input": True,
            "enable_audio_output": True,
            "tts_auto_execute": True,
        }
    )

    assert provider._client is not None  # noqa: SLF001 - accessed for assertions
    payload = json.loads(provider._client.sent[0])
    turn_detection = payload["session"]["audio"]["input"]["turn_detection"]
    assert turn_detection is None


async def test_receive_events_translates_openai_payloads() -> None:
    audio_chunk = base64.b64encode(b"hello").decode()
    messages = [
        json.dumps(
            {
                "type": "response.output_text.delta",
                "response": {"id": "resp_1"},
                "delta": {"text": "Hi"},
            }
        ),
        json.dumps(
            {
                "type": "response.output_audio.delta",
                "response": {"id": "resp_1"},
                "delta": {"audio": {"data": audio_chunk, "format": "pcm16"}},
            }
        ),
        json.dumps(
            {
                "type": "conversation.item.input_audio_transcription.completed",
                "item": {"id": "item_1"},
                "transcript": {"text": "Hello"},
            }
        ),
        json.dumps(
            {
                "type": "response.completed",
                "response": {"id": "resp_1", "status": "completed"},
            }
        ),
    ]

    provider = OpenAIRealtimeProvider(api_key="key", connect=_connect_factory(messages))
    await provider.open_session(settings={})

    events = [event async for event in provider.receive_events()]
    assert [event.type for event in events] == [
        RealtimeEventType.MESSAGE,
        RealtimeEventType.AUDIO_CHUNK,
        RealtimeEventType.MESSAGE,
        RealtimeEventType.CONTROL,
    ]
    assert events[0].payload["text"] == "Hi"
    assert events[1].payload["audio"] == audio_chunk
    assert events[2].payload["text"] == "Hello"
    assert events[3].payload["status"] == "completed"


async def test_send_user_event_supports_binary_payload() -> None:
    connection = DummyConnection()

    async def _connect(url: str, **_: Mapping[str, object]) -> DummyConnection:
        return connection

    provider = OpenAIRealtimeProvider(api_key="key", connect=_connect)
    await provider.open_session(settings={})

    await provider.send_user_event({"binary": b"audio-bytes"})
    await provider.send_user_event({"type": "input"})

    # First message is the session.update emitted during open_session
    assert connection.sent[1] == b"audio-bytes"
    assert json.loads(connection.sent[2]) == {"type": "input"}


async def test_create_conversation_item_user_role_uses_input_text() -> None:
    connection = DummyConnection()

    async def _connect(url: str, **_: Mapping[str, object]) -> DummyConnection:
        return connection

    provider = OpenAIRealtimeProvider(api_key="key", connect=_connect)
    await provider.open_session(settings={})

    await provider.create_conversation_item(text="Hello", role="user")

    payload = json.loads(connection.sent[-1])
    assert payload["item"]["role"] == "user"
    assert payload["item"]["content"] == [
        {"type": "input_text", "text": "Hello"}
    ]


async def test_create_conversation_item_assistant_role_uses_text_type() -> None:
    connection = DummyConnection()

    async def _connect(url: str, **_: Mapping[str, object]) -> DummyConnection:
        return connection

    provider = OpenAIRealtimeProvider(api_key="key", connect=_connect)
    await provider.open_session(settings={})

    await provider.create_conversation_item(text="Hi there", role="assistant")

    payload = json.loads(connection.sent[-1])
    assert payload["item"]["role"] == "assistant"
    assert payload["item"]["content"] == [
        {"type": "output_text", "text": "Hi there"}
    ]


async def test_cancel_turn_emits_cancel_event() -> None:
    connection = DummyConnection(
        [
            json.dumps(
                {
                    "type": "response.output_text.delta",
                    "response": {"id": "resp_cancel"},
                    "delta": {"text": "hello"},
                }
            )
        ]
    )

    async def _connect(url: str, **_: Mapping[str, object]) -> DummyConnection:
        return connection

    provider = OpenAIRealtimeProvider(api_key="key", connect=_connect)
    await provider.open_session(settings={})
    # Drain events to ensure current response id is captured
    async for _ in provider.receive_events():
        break

    await provider.cancel_turn()
    assert json.loads(connection.sent[-1]) == {
        "type": "response.cancel",
        "response_id": "resp_cancel",
    }


async def test_drain_audio_queue_triggers_response_when_vad_disabled() -> None:
    provider = OpenAIRealtimeProvider(api_key="key", connect=_connect_factory())
    await provider.open_session(
        settings={
            "model": "gpt-realtime",
            "vad_enabled": False,
            "enable_audio_input": True,
            "enable_audio_output": False,
        }
    )

    queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    await provider.set_input_audio_queue(queue)
    await queue.put(b"chunk")
    await queue.put(None)

    drain_task = asyncio.create_task(provider._drain_audio_queue())  # noqa: SLF001 - testing private method
    await asyncio.wait_for(drain_task, timeout=1.0)

    # First message is session.update, remaining messages are from drain task
    payloads = [json.loads(message) for message in provider._client.sent[1:]]  # type: ignore[union-attr]
    types = [payload.get("type") for payload in payloads]
    assert "input_audio_buffer.commit" in types
    assert "response.create" in types

    response_payload = next(
        payload for payload in payloads if payload.get("type") == "response.create"
    )
    assert response_payload["response"]["output_modalities"] == ["text"]


async def test_drain_audio_queue_does_not_trigger_response_when_vad_enabled() -> None:
    provider = OpenAIRealtimeProvider(api_key="key", connect=_connect_factory())
    await provider.open_session(
        settings={
            "model": "gpt-realtime",
            "vad_enabled": True,
            "enable_audio_input": True,
            "enable_audio_output": False,
        }
    )

    queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    await provider.set_input_audio_queue(queue)
    await queue.put(b"chunk")
    await queue.put(None)

    drain_task = asyncio.create_task(provider._drain_audio_queue())  # noqa: SLF001 - testing private method
    await asyncio.wait_for(drain_task, timeout=1.0)

    payloads = [json.loads(message) for message in provider._client.sent[1:]]  # type: ignore[union-attr]
    types = [payload.get("type") for payload in payloads]
    assert "input_audio_buffer.commit" not in types
    assert "response.create" not in types


async def test_request_response_uses_helper_event() -> None:
    provider = OpenAIRealtimeProvider(api_key="key", connect=_connect_factory())
    await provider.open_session(
        settings={
            "model": "gpt-realtime",
            "vad_enabled": True,
            "enable_audio_input": True,
            "enable_audio_output": True,
            "tts_auto_execute": True,
        }
    )

    await provider.request_response()

    payload = json.loads(provider._client.sent[-1])  # type: ignore[union-attr]
    assert payload["type"] == "response.create"
    assert payload["response"]["output_modalities"] == ["audio"]
