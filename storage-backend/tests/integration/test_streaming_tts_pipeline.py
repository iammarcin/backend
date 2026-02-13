"""Integration tests for the restored streaming TTS pipeline."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict
from unittest.mock import AsyncMock

import pytest

from core.exceptions import ProviderError
from core.streaming.manager import StreamingManager
from features.chat.services.streaming.service import ChatService

from tests.utils.streaming_tts_test_helpers import (
    StubTTSService,
    install_streaming_stubs,
    make_settings,
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tts_disabled_works(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disabling TTS should not break streaming responses."""

    install_streaming_stubs(monkeypatch, text_chunks=["Hello ", "world."])

    manager = StreamingManager()
    manager.add_queue(asyncio.Queue())

    chat_service = ChatService(tts_service=StubTTSService())
    settings = make_settings(streaming_enabled=True, tts_auto_execute=False)

    result = await chat_service.stream_response(
        prompt="Hello world",
        settings=settings,
        customer_id=7,
        manager=manager,
        timings={},
    )

    assert "tts" not in result or result["tts"] is None
    assert result["text_response"].strip() == "Hello world."


@pytest.mark.integration
@pytest.mark.asyncio
async def test_text_generation_error_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    """The orchestrator should clean up TTS resources when text streaming fails."""

    install_streaming_stubs(monkeypatch, text_chunks=["partial", "chunk"])

    async def failing_collect(**kwargs):  # type: ignore[override]
        manager: StreamingManager = kwargs["manager"]
        timings: Dict[str, float] = kwargs["timings"]
        timings["text_first_chunk_time"] = time.time()
        await manager.send_to_queues({"type": "text_chunk", "content": "partial"})
        raise RuntimeError("text generation failed")

    monkeypatch.setattr(
        "features.chat.services.streaming.core.collect_streaming_chunks",
        failing_collect,
    )

    manager = StreamingManager()
    manager.add_queue(asyncio.Queue())

    chat_service = ChatService(tts_service=StubTTSService())
    settings = make_settings(streaming_enabled=True, tts_auto_execute=True)

    with pytest.raises(ProviderError) as exc_info:
        await chat_service.stream_response(
            prompt="Trigger failure",
            settings=settings,
            customer_id=2,
            manager=manager,
            timings={},
        )

    assert "Streaming failed" in str(exc_info.value)
    assert not manager.is_tts_enabled()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tts_provider_error_doesnt_fail_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TTS failures should not cancel the chat response."""

    install_streaming_stubs(monkeypatch, text_chunks=["chunk", "two"])

    manager = StreamingManager()
    manager.add_queue(asyncio.Queue())

    chat_service = ChatService(tts_service=StubTTSService())
    monkeypatch.setattr(
        chat_service._tts_service,
        "stream_from_text_queue",
        AsyncMock(side_effect=RuntimeError("TTS failed")),
    )
    monkeypatch.setattr(
        "features.chat.services.streaming.payload.maybe_stream_tts",
        AsyncMock(return_value=None),
    )

    settings = make_settings(streaming_enabled=True, tts_auto_execute=True)

    result = await chat_service.stream_response(
        prompt="Test",
        settings=settings,
        customer_id=3,
        manager=manager,
        timings={},
    )

    assert "text_response" in result
    assert result["text_response"].strip() == "chunktwo"
    assert result.get("tts") is None
