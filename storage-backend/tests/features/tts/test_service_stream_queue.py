"""Tests for queue-based TTS streaming service helpers."""

from __future__ import annotations

import asyncio
import base64
import sys
import types
from typing import Any

import pytest

from core.exceptions import ValidationError
from core.streaming.manager import StreamingManager

if "features.chat.services.streaming" not in sys.modules:
    import features.chat.services  # type: ignore import

    streaming_stub = types.ModuleType("features.chat.services.streaming")
    streaming_stub.__path__ = []  # type: ignore[attr-defined]

    events_stub = types.ModuleType("features.chat.services.streaming.events")

    async def _noop_emit_tool_use_event(*args: Any, **kwargs: Any) -> None:  # pragma: no cover - simple stub
        return None

    events_stub.emit_tool_use_event = _noop_emit_tool_use_event  # type: ignore[attr-defined]

    sys.modules["features.chat.services.streaming"] = streaming_stub
    sys.modules["features.chat.services.streaming.events"] = events_stub
    setattr(sys.modules["features.chat.services"], "streaming", streaming_stub)
    streaming_stub.events = events_stub  # type: ignore[attr-defined]

from features.tts.service import TTSService
from features.tts.service_models import TTSStreamingMetadata
from features.tts.schemas.requests import (
    TTSGeneralSettings,
    TTSProviderSettings,
    TTSUserSettings,
)

import features.tts.service_stream_queue as queue_module


class _FakeStreamingProvider:
    name = "fake-stream"
    supports_input_stream = True

    def __init__(self) -> None:
        self.consumed: list[str] = []

    def get_websocket_format(self) -> str:
        return "pcm_24000"

    async def stream_from_text_queue(
        self,
        *,
        text_queue: asyncio.Queue[str | None],
        voice: str | None,
        model: str | None,
        audio_format: str,
        voice_settings: dict[str, Any],
        chunk_length_schedule: list[int] | None,
    ):
        while True:
            item = await text_queue.get()
            if item is None:
                break
            self.consumed.append(item)
            payload = base64.b64encode(f"audio:{item}".encode()).decode()
            yield payload


class _FakeFallbackProvider:
    name = "fallback"
    supports_input_stream = False

    def get_websocket_format(self) -> str:
        return "pcm"


class _SilentStreamingProvider:
    name = "silent"
    supports_input_stream = True

    def get_websocket_format(self) -> str:
        return "pcm"

    async def stream_from_text_queue(
        self,
        *,
        text_queue: asyncio.Queue[str | None],
        voice: str | None,
        model: str | None,
        audio_format: str,
        voice_settings: dict[str, Any],
        chunk_length_schedule: list[int] | None,
    ):
        # Drain the queue without yielding audio to simulate provider failure.
        while True:
            item = await text_queue.get()
            if item is None:
                break
            # skip producing audio
        if False:
            yield  # pragma: no cover - keeps function an async generator


@pytest.mark.anyio("asyncio")
async def test_stream_from_text_queue_streams_audio_chunks() -> None:
    provider = _FakeStreamingProvider()
    service = TTSService(provider_resolver=lambda _: provider)

    manager = StreamingManager()
    frontend_queue: asyncio.Queue = asyncio.Queue()
    manager.add_queue(frontend_queue)

    text_queue: asyncio.Queue[str | None] = asyncio.Queue()
    manager.register_tts_queue(text_queue)

    user_settings = TTSUserSettings(
        general=TTSGeneralSettings(save_to_s3=False),
        tts=TTSProviderSettings(
            provider="elevenlabs",
            voice="sarah",
            model="eleven_turbo_v2",
            format="pcm",
        ),
    )

    await text_queue.put("Hello ")
    await text_queue.put("world")
    await text_queue.put(None)

    metadata = await service.stream_from_text_queue(
        text_queue=text_queue,
        customer_id=7,
        user_settings=user_settings,
        manager=manager,
    )

    events: list[dict[str, Any]] = []
    while not frontend_queue.empty():
        item = await frontend_queue.get()
        if isinstance(item, dict):
            events.append(item)

    audio_events = [event for event in events if event.get("type") == "audio_chunk"]

    assert provider.consumed == ["Hello ", "world"]
    assert metadata.provider == provider.name
    assert metadata.audio_chunk_count == 2
    assert any(event.get("type") == "tts_started" for event in events)
    assert any(event.get("type") == "tts_generation_completed" for event in events)
    assert audio_events and len(audio_events) == 2


@pytest.mark.anyio("asyncio")
async def test_stream_from_text_queue_falls_back_when_provider_lacks_support(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _FakeFallbackProvider()
    service = TTSService(provider_resolver=lambda _: provider)

    manager = StreamingManager()
    frontend_queue: asyncio.Queue = asyncio.Queue()
    manager.add_queue(frontend_queue)

    text_queue: asyncio.Queue[str | None] = asyncio.Queue()

    await text_queue.put("Hello")
    await text_queue.put("!")
    await text_queue.put(None)

    captured: dict[str, Any] = {}

    async def fake_fallback_stream(**kwargs: Any) -> TTSStreamingMetadata:
        captured.update(kwargs)
        return TTSStreamingMetadata(
            provider="fallback",
            model="mock",
            voice="voice",
            format="mp3",
            text_chunk_count=1,
            audio_chunk_count=1,
        )

    monkeypatch.setattr(
        queue_module,
        "perform_fallback_buffered_stream",
        fake_fallback_stream,
    )

    user_settings = TTSUserSettings(
        general=TTSGeneralSettings(save_to_s3=False),
        tts=TTSProviderSettings(provider="openai", voice="alloy"),
    )

    metadata = await service.stream_from_text_queue(
        text_queue=text_queue,
        customer_id=3,
        user_settings=user_settings,
        manager=manager,
    )

    assert metadata.provider == "fallback"
    assert captured.get("text_queue") is text_queue
    assert captured.get("customer_id") == 3
    assert captured.get("user_settings") is user_settings
    assert captured.get("provider") is provider


@pytest.mark.anyio("asyncio")
async def test_stream_from_text_queue_raises_when_no_audio_produced() -> None:
    provider = _SilentStreamingProvider()
    service = TTSService(provider_resolver=lambda _: provider)

    manager = StreamingManager()
    frontend_queue: asyncio.Queue = asyncio.Queue()
    manager.add_queue(frontend_queue)

    text_queue: asyncio.Queue[str | None] = asyncio.Queue()
    manager.register_tts_queue(text_queue)
    await text_queue.put(None)

    user_settings = TTSUserSettings(
        general=TTSGeneralSettings(save_to_s3=False),
        tts=TTSProviderSettings(provider="elevenlabs", voice="sarah"),
    )

    with pytest.raises(ValidationError):
        await service.stream_from_text_queue(
            text_queue=text_queue,
            customer_id=99,
            user_settings=user_settings,
            manager=manager,
        )
