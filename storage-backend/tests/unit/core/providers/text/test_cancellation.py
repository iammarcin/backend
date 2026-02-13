import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from core.providers.text.openai import OpenAITextProvider
from features.chat.utils.websocket_runtime import WorkflowRuntime


@pytest.mark.asyncio
async def test_openai_stream_cancellation():
    """Test that OpenAI stream stops when runtime is cancelled."""

    # Setup - Mock OpenAI client
    mock_client = AsyncMock()
    mock_client.chat = AsyncMock()
    mock_client.chat.completions = AsyncMock()

    # Mock streaming response
    async def mock_stream():
        yield MagicMock(choices=[MagicMock(delta=MagicMock(content="chunk1"))])
        yield MagicMock(choices=[MagicMock(delta=MagicMock(content="chunk2"))])
        await asyncio.sleep(10)  # Simulate long response
        yield MagicMock(choices=[MagicMock(delta=MagicMock(content="chunk3"))])

    mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())

    # Patch ai_clients at the point where it's imported (in the provider module)
    with patch('core.providers.text.openai.ai_clients', {"openai_async": mock_client}):
        provider = OpenAITextProvider()

        runtime = WorkflowRuntime(
            manager=MagicMock(),
            tasks=[],
            frontend_queue=asyncio.Queue(),
        )

        # Mock client to yield chunks slowly
        mock_stream_obj = AsyncMock()
        mock_stream_obj.__aiter__.return_value = [
            MagicMock(choices=[MagicMock(delta=MagicMock(content="chunk1"))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content="chunk2"))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content="chunk3"))]),
        ]
        provider.client.chat.completions.create = AsyncMock(return_value=mock_stream_obj)

        # Start streaming in background
        chunks = []

        async def stream_collector():
            async for chunk in provider.stream(
                prompt="test",
                model="gpt-4o-mini",
                runtime=runtime,
            ):
                chunks.append(chunk)
                await asyncio.sleep(0.1)  # Simulate slow streaming

        stream_task = asyncio.create_task(stream_collector())

        # Cancel after collecting some chunks
        await asyncio.sleep(0.15)  # Let it collect 1-2 chunks
        runtime.cancel()

        # Wait for stream to stop
        await asyncio.sleep(0.2)

        # Verify
        assert len(chunks) < 3, "Stream should stop before all chunks"
        assert runtime.is_cancelled()


# Similar tests for Anthropic, Gemini, xAI, etc.
@pytest.mark.asyncio
async def test_anthropic_stream_cancellation():
    """Test that Anthropic stream stops when runtime is cancelled."""
    from core.providers.text.anthropic import AnthropicTextProvider

    runtime = WorkflowRuntime(
        manager=MagicMock(),
        tasks=[],
        frontend_queue=asyncio.Queue(),
    )

    # Mock the streaming response
    mock_event_stream = AsyncMock()
    mock_event_stream.__aenter__ = AsyncMock(return_value=mock_event_stream)
    mock_event_stream.__aexit__ = AsyncMock(return_value=None)

    # Mock events - use async generator for proper iteration
    async def mock_aiter():
        events = [
            MagicMock(type="content_block_start", content_block=MagicMock(type="text", index=0)),
            MagicMock(type="content_block_delta", delta=MagicMock(type="text_delta", text="chunk1", index=0)),
            MagicMock(type="content_block_delta", delta=MagicMock(type="text_delta", text="chunk2", index=0)),
            MagicMock(type="content_block_delta", delta=MagicMock(type="text_delta", text="chunk3", index=0)),
        ]
        for event in events:
            yield event

    mock_event_stream.__aiter__ = mock_aiter

    # Mock client with proper context manager to avoid polluting global state
    mock_client = MagicMock()
    mock_client.messages.stream = MagicMock(return_value=mock_event_stream)

    with patch('core.providers.text.anthropic.ai_clients', {"anthropic_async": mock_client}):
        provider = AnthropicTextProvider()

        chunks = []

        async def stream_collector():
            async for chunk in provider.stream(
                prompt="test",
                model="claude-sonnet-4-5",
                runtime=runtime,
            ):
                chunks.append(chunk)
                await asyncio.sleep(0.1)

        stream_task = asyncio.create_task(stream_collector())

        await asyncio.sleep(0.15)
        runtime.cancel()
        await asyncio.sleep(0.2)

        assert len(chunks) < 3, "Stream should stop before all chunks"
        assert runtime.is_cancelled()
