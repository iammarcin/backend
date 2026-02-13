"""Regression tests for requires_action handling in standard_provider."""

from __future__ import annotations

from typing import Any, Dict, List

import pytest
from unittest.mock import AsyncMock, MagicMock

from features.chat.services.streaming.standard_provider import stream_standard_response


class _StubProvider:
    provider_name = "test_provider"

    def __init__(self, chunks: List[Any]):
        self._chunks = chunks

    async def stream(self, **_: Any):
        for chunk in self._chunks:
            yield chunk

    def get_model_config(self) -> Dict[str, Any]:  # pragma: no cover - helper
        return {}


@pytest.fixture(autouse=True)
def _patch_event_emitters(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _noop(*_: Any, **__: Any) -> None:  # pragma: no cover - helper
        return None

    # Only patch reasoning emitter - tool events should go through
    monkeypatch.setattr(
        "features.chat.services.streaming.standard_provider.emit_reasoning_custom_event",
        _noop,
    )


@pytest.fixture()
def streaming_manager() -> MagicMock:
    manager = MagicMock()
    manager.send_to_queues = AsyncMock()
    manager.collect_chunk = MagicMock()
    manager.collect_tool_call = MagicMock()
    return manager


@pytest.mark.asyncio
async def test_requires_action_true_awaits_client(streaming_manager: MagicMock) -> None:
    """Client-side tools must pause completion events until the client responds."""

    provider = _StubProvider(
        [
            {
                "type": "tool_call",
                "content": {
                    "toolName": "client_tool",
                    "callId": "call_123",
                    "requires_action": True,
                },
            },
            "ignored text",
        ]
    )

    outcome = await stream_standard_response(
        provider=provider,
        manager=streaming_manager,
        prompt_text="Hello",
        model="dummy",
        temperature=0.0,
        max_tokens=32,
        system_prompt=None,
    )

    assert outcome.requires_tool_action is True
    assert len(outcome.tool_calls) == 1
    streaming_manager.collect_tool_call.assert_called_once()

    # ToolCall events are sent only when the client must execute the tool
    sent_types = [call.args[0].get("type") for call in streaming_manager.send_to_queues.await_args_list]
    assert "tool_start" in sent_types


@pytest.mark.asyncio
async def test_requires_action_false_treated_as_server_side(streaming_manager: MagicMock) -> None:
    """Server-side tools keep streaming enabled and never emit toolCall frames."""

    provider = _StubProvider(
        [
            {
                "type": "tool_call",
                "content": {
                    "toolName": "server_tool",
                    "callId": "call_456",
                    "requires_action": False,
                },
            },
            "final text",
        ]
    )

    outcome = await stream_standard_response(
        provider=provider,
        manager=streaming_manager,
        prompt_text="Hello",
        model="dummy",
        temperature=0.0,
        max_tokens=32,
        system_prompt=None,
    )

    assert outcome.requires_tool_action is False
    assert outcome.text_chunks == ["final text"]
    sent_types = [call.args[0].get("type") for call in streaming_manager.send_to_queues.await_args_list]
    assert "tool_start" not in sent_types


@pytest.mark.asyncio
async def test_requires_action_none_defaults_to_server_side(streaming_manager: MagicMock) -> None:
    """Missing requires_action flag should behave like requires_action=False."""

    provider = _StubProvider(
        [
            {
                "type": "tool_call",
                "content": {
                    "toolName": "implicit_server_tool",
                    "callId": "call_789",
                    # Flag omitted on purpose
                },
            },
            "final text",
        ]
    )

    outcome = await stream_standard_response(
        provider=provider,
        manager=streaming_manager,
        prompt_text="Hello",
        model="dummy",
        temperature=0.0,
        max_tokens=32,
        system_prompt=None,
    )

    assert outcome.requires_tool_action is False
    assert outcome.text_chunks == ["final text"]
    sent_types = [call.args[0].get("type") for call in streaming_manager.send_to_queues.await_args_list]
    assert "tool_start" not in sent_types
