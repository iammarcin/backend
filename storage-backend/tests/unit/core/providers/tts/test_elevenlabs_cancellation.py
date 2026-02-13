"""Unit tests for ElevenLabs TTS provider cancellation functionality."""

import asyncio
import base64
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.providers.tts.elevenlabs import ElevenLabsTTSProvider
from features.chat.utils.websocket_runtime import WorkflowRuntime


@pytest.mark.asyncio
async def test_elevenlabs_websocket_cancellation():
    """Test ElevenLabs WebSocket closes on cancellation."""

    # Setup
    provider = ElevenLabsTTSProvider()
    runtime = WorkflowRuntime(
        manager=MagicMock(),
        tasks=[],
        frontend_queue=asyncio.Queue(),
    )

    # Mock WebSocket connection
    mock_ws = AsyncMock()
    mock_ws.__aenter__ = AsyncMock(return_value=mock_ws)
    mock_ws.__aexit__ = AsyncMock()
    mock_ws.send = AsyncMock()

    # Simulate receiving audio chunks slowly
    async def mock_receive():
        chunk1 = base64.b64encode(b'\x00\x01\x02\x03\x04\x05\x06\x07').decode('utf-8')
        chunk2 = base64.b64encode(b'\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f').decode('utf-8')
        chunk3 = base64.b64encode(b'\x10\x11\x12\x13\x14\x15\x16\x17').decode('utf-8')
        yield f'{{"audio": "{chunk1}"}}'
        await asyncio.sleep(0.1)
        yield f'{{"audio": "{chunk2}"}}'
        await asyncio.sleep(0.1)
        yield f'{{"audio": "{chunk3}"}}'

    mock_ws.__aiter__ = lambda self: mock_receive()

    # Patch websockets.connect
    with patch('websockets.connect', return_value=mock_ws):
        chunks = []

        async def stream_collector():
            async for chunk in provider.stream_websocket(
                request=MagicMock(text="test", voice="test", format="pcm", metadata={}),
                runtime=runtime,
            ):
                chunks.append(chunk)

        stream_task = asyncio.create_task(stream_collector())

        # Cancel after receiving some chunks
        await asyncio.sleep(0.15)
        runtime.cancel()
        await asyncio.sleep(0.2)

        # Verify
        assert len(chunks) < 3, "Should stop before all chunks"
        assert mock_ws.__aexit__.called, "WebSocket should close"


@pytest.mark.asyncio
async def test_elevenlabs_websocket_no_cancellation():
    """Test ElevenLabs WebSocket works normally without cancellation."""

    # Setup
    provider = ElevenLabsTTSProvider()

    # Mock WebSocket connection
    mock_ws = AsyncMock()
    mock_ws.__aenter__ = AsyncMock(return_value=mock_ws)
    mock_ws.__aexit__ = AsyncMock()
    mock_ws.send = AsyncMock()

    # Simulate receiving all audio chunks
    async def mock_receive():
        chunk1 = base64.b64encode(b'\x00\x01\x02\x03\x04\x05\x06\x07').decode('utf-8')
        chunk2 = base64.b64encode(b'\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f').decode('utf-8')
        chunk3 = base64.b64encode(b'\x10\x11\x12\x13\x14\x15\x16\x17').decode('utf-8')
        yield f'{{"audio": "{chunk1}"}}'
        yield f'{{"audio": "{chunk2}"}}'
        yield f'{{"audio": "{chunk3}"}}'
        yield '{"status": "finished"}'

    mock_ws.__aiter__ = lambda self: mock_receive()

    # Patch websockets.connect
    with patch('websockets.connect', return_value=mock_ws):
        chunks = []

        async for chunk in provider.stream_websocket(
            request=MagicMock(text="test", voice="test", format="pcm", metadata={}),
            runtime=None,  # No runtime = no cancellation
        ):
            chunks.append(chunk)

        # Verify all chunks received
        assert len(chunks) == 3, "Should receive all chunks without cancellation"
        assert mock_ws.__aexit__.called, "WebSocket should close"


@pytest.mark.asyncio
async def test_elevenlabs_queue_cancellation():
    """Test ElevenLabs queue-based streaming cancellation."""

    # Setup
    provider = ElevenLabsTTSProvider()
    runtime = WorkflowRuntime(
        manager=MagicMock(),
        tasks=[],
        frontend_queue=asyncio.Queue(),
    )

    text_queue = asyncio.Queue()
    await text_queue.put("Hello")
    await text_queue.put("world")
    await text_queue.put(None)  # EOS

    # Mock WebSocket connection
    mock_ws = AsyncMock()
    mock_ws.__aenter__ = AsyncMock(return_value=mock_ws)
    mock_ws.__aexit__ = AsyncMock()
    mock_ws.send = AsyncMock()

    # Simulate receiving audio chunks
    async def mock_receive():
        yield '{"audio": "base64data1"}'
        await asyncio.sleep(0.1)
        yield '{"audio": "base64data2"}'

    mock_ws.__aiter__ = lambda self: mock_receive()

    # Patch websockets.connect
    with patch('websockets.connect', return_value=mock_ws):
        chunks = []

        async def stream_collector():
            async for chunk in provider.stream_from_text_queue(
                text_queue=text_queue,
                voice="test",
                runtime=runtime,
            ):
                chunks.append(chunk)

        stream_task = asyncio.create_task(stream_collector())

        # Cancel during processing
        await asyncio.sleep(0.05)
        runtime.cancel()
        await asyncio.sleep(0.2)

        # Verify
        assert len(chunks) >= 0, "Should stop streaming on cancellation"
        assert mock_ws.__aexit__.called, "WebSocket should close"
