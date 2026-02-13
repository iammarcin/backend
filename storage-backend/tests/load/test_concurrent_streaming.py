"""Load tests ensuring the streaming pipeline handles concurrent requests."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Tuple

import pytest

from core.streaming.manager import StreamingManager
from features.chat.services.streaming.service import ChatService

from tests.utils.streaming_tts_test_helpers import (
    StubTTSService,
    install_streaming_stubs,
    make_settings,
)


@pytest.mark.load
@pytest.mark.asyncio
async def test_concurrent_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure multiple concurrent streaming requests complete successfully."""

    install_streaming_stubs(
        monkeypatch,
        text_chunks=["Request ", "response."],
        text_delay=0.002,
    )

    async def single_request(request_id: int) -> Tuple[int, Dict[str, Any]]:
        manager = StreamingManager()
        manager.add_queue(asyncio.Queue())

        service = ChatService(tts_service=StubTTSService(audio_delay=0.005))
        result = await service.stream_response(
            prompt=f"Request {request_id}: Tell me a joke",
            settings=make_settings(streaming_enabled=True, tts_auto_execute=True),
            customer_id=request_id,
            manager=manager,
            timings={},
        )
        return request_id, result

    num_requests = 10
    tasks: List[asyncio.Task[Tuple[int, Dict[str, Any]]]] = [
        asyncio.create_task(single_request(i)) for i in range(num_requests)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)
    successes = [item for item in results if not isinstance(item, Exception)]

    assert len(successes) == num_requests
    for request_id, payload in successes:
        assert payload["text_response"].startswith("Request")
        assert "tts" in payload and payload["tts"] is not None
