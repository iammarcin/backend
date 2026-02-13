"""Tests for Gemini operations."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.providers.text.gemini import GeminiTextProvider


@pytest.mark.asyncio
async def test_gemini_thinking_emission():
    """Test that Gemini thinking parts are yielded as reasoning events."""
    provider = GeminiTextProvider()

    # Mock Gemini SDK types
    ThinkingPart = MagicMock()
    ThinkingPart.text = "Let me analyze this problem..."
    ThinkingPart.thought = True

    TextPart = MagicMock()
    TextPart.text = "Based on my analysis, the answer is 42."
    TextPart.thought = False

    # Mock chunk structure
    mock_chunks = [
        MagicMock(
            candidates=[
                MagicMock(
                    content=MagicMock(parts=[ThinkingPart])
                )
            ],
            text=None  # text attribute is None when parts exist
        ),
        MagicMock(
            candidates=[
                MagicMock(
                    content=MagicMock(parts=[TextPart])
                )
            ],
            text=None
        ),
    ]

    async def mock_stream():
        for chunk in mock_chunks:
            yield chunk

    mock_async_client = MagicMock()
    mock_async_client.models.generate_content_stream = AsyncMock(
        return_value=mock_stream()
    )

    with patch.object(provider, '_get_async_client', return_value=mock_async_client):
        chunks = []
        async for chunk in provider.stream(
            prompt="test",
            enable_reasoning=True,
            reasoning_value=5,  # thinking token budget
        ):
            chunks.append(chunk)

    # Verify thinking and text chunks
    reasoning_chunks = [c for c in chunks if isinstance(c, dict) and c.get("type") == "reasoning"]
    text_chunks = [c for c in chunks if isinstance(c, str)]

    assert len(reasoning_chunks) == 1, f"Expected 1 reasoning chunk, got {len(reasoning_chunks)}"
    assert reasoning_chunks[0]["content"] == "Let me analyze this problem..."

    assert len(text_chunks) == 1, f"Expected 1 text chunk, got {len(text_chunks)}"
    assert text_chunks[0] == "Based on my analysis, the answer is 42."


@pytest.mark.asyncio
async def test_gemini_fallback_to_chunk_text():
    """Test that chunk.text is used as fallback when parts are not available."""
    provider = GeminiTextProvider()

    # Mock chunk with text but no parts
    mock_chunks = [
        MagicMock(
            candidates=None,  # No candidates
            text="Regular response text"
        ),
    ]

    async def mock_stream():
        for chunk in mock_chunks:
            yield chunk

    mock_async_client = MagicMock()
    mock_async_client.models.generate_content_stream = AsyncMock(
        return_value=mock_stream()
    )

    with patch.object(provider, '_get_async_client', return_value=mock_async_client):
        chunks = []
        async for chunk in provider.stream(
            prompt="test",
            enable_reasoning=False,
        ):
            chunks.append(chunk)

    # Should get the text chunk
    assert len(chunks) == 1
    assert chunks[0] == "Regular response text"
