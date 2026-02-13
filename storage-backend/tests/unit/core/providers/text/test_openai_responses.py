"""Tests for OpenAI Responses API streaming functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from core.providers.text.openai_responses.stream import stream_responses_api


@pytest.mark.asyncio
async def test_responses_api_reasoning_emission():
    """Test that reasoning deltas are yielded correctly."""
    mock_client = MagicMock()

    # Mock response stream with reasoning events
    async def mock_stream():
        # Regular text event
        yield MagicMock(type="response.delta", delta="Hello")
        # Reasoning events using output_item.added
        reasoning_item1 = MagicMock()
        reasoning_item1.type = "reasoning"
        reasoning_item1.summary = "Let me think..."
        yield MagicMock(type="response.output_item.added", item=reasoning_item1)
        reasoning_item2 = MagicMock()
        reasoning_item2.type = "reasoning"
        reasoning_item2.summary = "Based on analysis..."
        yield MagicMock(type="response.output_item.added", item=reasoning_item2)
        # More text
        yield MagicMock(type="response.delta", delta=" world")

    mock_client.responses.create = AsyncMock(return_value=mock_stream())

    chunks = []
    async for chunk in stream_responses_api(
        client=mock_client,
        model_config=None,
        messages=[{"role": "user", "content": "test"}],
        model="o3-mini",
        temperature=1.0,
        max_tokens=1000,
        enable_reasoning=True,
        reasoning_effort="medium",
    ):
        chunks.append(chunk)

    # Verify we got text and reasoning chunks
    text_chunks = [c for c in chunks if isinstance(c, str)]
    reasoning_chunks = [c for c in chunks if isinstance(c, dict) and c.get("type") == "reasoning"]

    assert len(text_chunks) == 2  # "Hello" and " world"
    assert len(reasoning_chunks) == 2  # Two reasoning events
    assert reasoning_chunks[0]["content"] == "Let me think..."
    assert reasoning_chunks[1]["content"] == "Based on analysis..."
