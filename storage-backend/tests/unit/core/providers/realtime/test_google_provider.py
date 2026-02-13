"""Unit tests for the Google realtime provider implementation."""

from __future__ import annotations

import base64
import json
from typing import Iterable, Mapping

import pytest
from websockets.exceptions import ConnectionClosedOK

from core.providers.realtime.base import RealtimeEventType
from core.providers.realtime.google import GoogleRealtimeProvider


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class DummyConnection:
    """Websocket stub for exercising the provider."""

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


async def test_open_session_sends_setup_message() -> None:
    provider = GoogleRealtimeProvider(api_key="key", connect=_connect_factory())

    await provider.open_session(
        settings={
            "model": "gemini-live-preview",
            "voice": "Puck",
            "temperature": 0.6,
            "enable_audio_input": True,
            "enable_audio_output": True,
            "tts_auto_execute": False,
        }
    )

    assert provider._client is not None  # noqa: SLF001 - accessed for assertions
    payload = json.loads(provider._client.sent[0])  # type: ignore[index]
    assert payload["setup"]["model"] == "gemini-live-preview"
    assert "response_modalities" in payload["setup"]["generation_config"]


async def test_receive_events_translates_gemini_payloads() -> None:
    audio_chunk = base64.b64encode(b"audio").decode()
    messages = [
        json.dumps(
            {
                "serverContent": {
                    "modelTurn": {
                        "parts": [
                            {"text": "Hello"},
                            {
                                "inlineData": {
                                    "data": audio_chunk,
                                    "mimeType": "audio/pcm",
                                }
                            },
                        ]
                    },
                    "turnComplete": True,
                }
            }
        )
    ]

    provider = GoogleRealtimeProvider(api_key="key", connect=_connect_factory(messages))
    await provider.open_session(settings={})

    events = [event async for event in provider.receive_events()]
    assert [event.type for event in events] == [
        RealtimeEventType.MESSAGE,
        RealtimeEventType.AUDIO_CHUNK,
        RealtimeEventType.MESSAGE,
        RealtimeEventType.AUDIO_CHUNK,
        RealtimeEventType.CONTROL,
    ]
    assert events[0].payload["text"] == "Hello"
    assert events[1].payload["audio"] == audio_chunk
    assert events[-1].payload["event"] == "turn.completed"


async def test_client_content_emits_user_transcripts() -> None:
    messages = [
        json.dumps(
            {
                "clientContent": {
                    "turns": [
                        {
                            "parts": [
                                {"text": "User said"},
                            ]
                        }
                    ],
                    "turnComplete": True,
                }
            }
        )
    ]

    provider = GoogleRealtimeProvider(api_key="key", connect=_connect_factory(messages))
    await provider.open_session(settings={})

    events = [event async for event in provider.receive_events()]
    assert len(events) == 2
    assert events[0].type == RealtimeEventType.MESSAGE
    assert events[0].payload["event"] == "user.transcript.delta"
    assert events[1].payload["event"] == "user.transcript.completed"
