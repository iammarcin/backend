"""Integration-style tests for non-agentic completion events."""

from __future__ import annotations

import asyncio
import sys
import types
from typing import Any, Dict, List

import pytest

# Avoid downloading tokenizer files during import by stubbing tiktoken before the
# chat service module tree is imported. The fallback encoding mimics the helper
# defined in features.semantic_search.utils.token_counter.
if "tiktoken" not in sys.modules:  # pragma: no cover - test environment helper
    fake_module = types.SimpleNamespace()

    class _FallbackEncoding:
        def encode(self, text: str) -> List[int]:  # type: ignore[name-defined]
            return [ord(char) for char in text]

        def decode(self, tokens: List[int]) -> str:  # type: ignore[name-defined]
            return "".join(chr(token) for token in tokens)

    def _get_encoding(_name: str) -> _FallbackEncoding:
        return _FallbackEncoding()

    fake_module.get_encoding = _get_encoding  # type: ignore[attr-defined]
    sys.modules["tiktoken"] = fake_module  # type: ignore[assignment]

from core.streaming.manager import StreamingManager
from features.chat.utils.websocket_workflow_executor import run_standard_workflow


class _StubChatService:
    def __init__(self, response_payload: Dict[str, Any]) -> None:
        self._response_payload = response_payload
        self.calls: int = 0

    async def stream_response(self, **_: Any) -> Dict[str, Any]:
        self.calls += 1
        return dict(self._response_payload)


class _StubSTTService:
    async def transcribe(self, *_: Any, **__: Any) -> Dict[str, Any]:  # pragma: no cover - unused helper
        return {}


async def _drain_events(queue: asyncio.Queue) -> List[Any]:
    events: List[Any] = []
    while True:
        item = await asyncio.wait_for(queue.get(), timeout=0.5)
        events.append(item)
        if item is None:
            break
    return events


async def _execute_workflow(response: Dict[str, Any]) -> List[Any]:
    manager = StreamingManager()
    queue: asyncio.Queue = asyncio.Queue()
    manager.add_queue(queue)
    token = manager.create_completion_token()
    service = _StubChatService(response_payload=response)

    await run_standard_workflow(
        request_type="text",
        prompt=[{"type": "text", "text": "Hi"}],
        settings={"text": {}, "tts": {"tts_auto_execute": False}},
        customer_id=42,
        manager=manager,
        service=service,
        stt_service=_StubSTTService(),
        websocket=object(),
        completion_token=token,
        data={"user_input": {}},
    )

    return await _drain_events(queue)


@pytest.mark.asyncio
async def test_server_side_tool_flow_sends_text_completed() -> None:
    events = await _execute_workflow({"requires_tool_action": False})
    event_types = [event.get("type") for event in events if isinstance(event, dict)]
    assert "text_completed" in event_types
    assert "tts_not_requested" in event_types


@pytest.mark.asyncio
async def test_client_side_tool_skips_text_completed_until_resume() -> None:
    events = await _execute_workflow({"requires_tool_action": True})
    event_types = [event.get("type") for event in events if isinstance(event, dict)]
    assert "text_completed" not in event_types
    assert "tts_not_requested" not in event_types


@pytest.mark.asyncio
async def test_text_only_request_behaves_like_server_side_tool() -> None:
    events = await _execute_workflow({})
    event_types = [event.get("type") for event in events if isinstance(event, dict)]
    assert "text_completed" in event_types
    assert "tts_not_requested" in event_types
