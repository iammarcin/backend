"""Tests for non-agentic standard provider streaming helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

import pytest

from features.chat.services.streaming.standard_provider import stream_standard_response


class DummyProvider:
    """Simple provider stub that yields predefined chunks."""

    provider_name = "dummy"

    def __init__(self, chunks: List[Any]) -> None:
        self._chunks = chunks

    async def stream(self, **_: Any):
        for chunk in self._chunks:
            yield chunk

    def get_model_config(self) -> Dict[str, Any]:  # pragma: no cover - simple stub
        return {}


@dataclass
class SentPayload:
    queue_type: str
    payload: Any


class DummyManager:
    """Streaming manager stub that records payloads."""

    def __init__(self) -> None:
        self.sent_payloads: List[SentPayload] = []
        self.tool_calls: List[Dict[str, Any]] = []
        self.chunks: Dict[str, List[str]] = {"text": [], "reasoning": []}

    async def send_to_queues(self, payload: Any, queue_type: str = "all") -> None:
        self.sent_payloads.append(SentPayload(queue_type=queue_type, payload=payload))

    def collect_tool_call(self, payload: Dict[str, Any]) -> None:
        self.tool_calls.append(payload)

    def collect_chunk(self, chunk: str, chunk_type: str = "text") -> None:
        self.chunks.setdefault(chunk_type, []).append(chunk)


@pytest.mark.asyncio
async def test_tool_call_requires_action_true_waits_for_client() -> None:
    """Tools that explicitly require action should trigger awaiting state."""

    chunks = [
        {
            "type": "tool_call",
            "content": {
                "toolName": "code_interpreter",
                "callId": "call-1",
                "requires_action": True,
            },
        },
        "ignored text",
    ]
    provider = DummyProvider(chunks)
    manager = DummyManager()

    result = await stream_standard_response(
        provider=provider,
        manager=manager,
        prompt_text="hello",
        model="dummy",
        temperature=0.0,
        max_tokens=16,
        system_prompt=None,
    )

    assert result.requires_tool_action is True
    assert result.text_chunks == []
    tool_call_events = [p for p in manager.sent_payloads if p.payload.get("type") == "tool_start"]
    assert len(tool_call_events) == 1


@pytest.mark.asyncio
async def test_tool_call_requires_action_false_treated_server_side() -> None:
    """requires_action=False should allow streaming to continue immediately."""

    chunks = [
        {
            "type": "tool_call",
            "content": {
                "toolName": "web_search",
                "callId": "call-2",
                "requires_action": False,
            },
        },
        "result text",
    ]
    provider = DummyProvider(chunks)
    manager = DummyManager()

    result = await stream_standard_response(
        provider=provider,
        manager=manager,
        prompt_text="hello",
        model="dummy",
        temperature=0.0,
        max_tokens=16,
        system_prompt=None,
    )

    assert result.requires_tool_action is False
    assert result.text_chunks == ["result text"]
    assert all(p.payload.get("type") != "tool_start" for p in manager.sent_payloads)


@pytest.mark.asyncio
async def test_tool_call_without_flag_defaults_to_server_side() -> None:
    """Missing requires_action should default to False (server-side)."""

    chunks = [
        {
            "type": "tool_call",
            "content": {
                "toolName": "web_search",
                "callId": "call-3",
            },
        },
        "final text",
    ]
    provider = DummyProvider(chunks)
    manager = DummyManager()

    result = await stream_standard_response(
        provider=provider,
        manager=manager,
        prompt_text="hello",
        model="dummy",
        temperature=0.0,
        max_tokens=16,
        system_prompt=None,
    )

    assert result.requires_tool_action is False
    assert result.text_chunks == ["final text"]
    assert all(p.payload.get("type") != "tool_start" for p in manager.sent_payloads)
