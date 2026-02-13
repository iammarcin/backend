"""Tests for Anthropic text provider."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.clients.ai import ai_clients
from core.providers.text.anthropic import AnthropicTextProvider


@pytest.fixture(autouse=True)
def mock_anthropic_client(monkeypatch):
    client = SimpleNamespace(
        messages=SimpleNamespace(
            create=AsyncMock(return_value=SimpleNamespace(content=[])),
            stream=MagicMock(),
        )
    )
    monkeypatch.setitem(ai_clients, "anthropic_async", client)
    return client


@pytest.mark.asyncio
async def test_anthropic_thinking_emission(mock_anthropic_client):
    """Test that thinking blocks are yielded as reasoning events."""
    provider = AnthropicTextProvider()

    # Create mock events
    events = [
        # Thinking block start
        MagicMock(type="content_block_start", index=0, content_block=MagicMock(type="thinking")),
        # Thinking deltas
        MagicMock(type="content_block_delta", index=0, delta=MagicMock(type="text_delta", text="Let me analyze...")),
        MagicMock(type="content_block_delta", index=0, delta=MagicMock(type="text_delta", text=" this problem.")),
        # Text block start
        MagicMock(type="content_block_start", index=1, content_block=MagicMock(type="text")),
        # Text deltas
        MagicMock(type="content_block_delta", index=1, delta=MagicMock(type="text_delta", text="Based on")),
        MagicMock(type="content_block_delta", index=1, delta=MagicMock(type="text_delta", text=" analysis.")),
    ]

    # Create a mock stream object that is async iterable
    class MockEventStream:
        def __init__(self, events):
            self.events = events

        def __aiter__(self):
            return self

        async def __anext__(self):
            if not self.events:
                raise StopAsyncIteration
            return self.events.pop(0)

        async def get_final_message(self):
            return None

    mock_event_stream = MockEventStream(events)

    # Mock the context manager
    mock_stream_context = MagicMock()
    mock_stream_context.__aenter__ = AsyncMock(return_value=mock_event_stream)
    mock_stream_context.__aexit__ = AsyncMock()

    provider.client.messages.stream = MagicMock(return_value=mock_stream_context)

    chunks = []
    async for chunk in provider.stream(
        prompt="test",
        enable_reasoning=True,
        reasoning_value=5000,
    ):
        chunks.append(chunk)

    # Verify thinking and text chunks
    reasoning_chunks = [c for c in chunks if isinstance(c, dict) and c.get("type") == "reasoning"]
    text_chunks = [c for c in chunks if isinstance(c, str)]

    assert len(reasoning_chunks) == 2, f"Expected 2 reasoning chunks, got {len(reasoning_chunks)}"
    assert reasoning_chunks[0]["content"] == "Let me analyze..."
    assert reasoning_chunks[1]["content"] == " this problem."

    assert len(text_chunks) == 2, f"Expected 2 text chunks, got {len(text_chunks)}"
    assert text_chunks[0] == "Based on"
    assert text_chunks[1] == " analysis."


@pytest.mark.asyncio
async def test_anthropic_disable_native_tools(mock_anthropic_client):
    provider = AnthropicTextProvider()
    mock_anthropic_client.messages.create = AsyncMock(return_value=SimpleNamespace(content=[]))

    await provider.generate(prompt="summarize this", disable_native_tools=True)

    kwargs = mock_anthropic_client.messages.create.await_args.kwargs
    assert kwargs["tools"] == []


@pytest.mark.asyncio
async def test_anthropic_default_tools_present(mock_anthropic_client):
    provider = AnthropicTextProvider()
    mock_anthropic_client.messages.create = AsyncMock(return_value=SimpleNamespace(content=[]))

    await provider.generate(prompt="summarize this")

    kwargs = mock_anthropic_client.messages.create.await_args.kwargs
    assert kwargs["tools"]
    assert kwargs["tools"][0]["name"] == "web_search"
