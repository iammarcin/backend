"""Tests for chat service image workflow."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from core.streaming.manager import StreamingManager
from features.chat.service import ChatService

pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture
def anyio_backend():
    """Limit AnyIO to asyncio backend for these tests."""

    return "asyncio"


async def test_stream_response_with_image_mode():
    """Should trigger image generation when image_mode detected."""

    service = ChatService()
    manager = StreamingManager()
    completion_token = manager.create_completion_token()
    frontend_queue: asyncio.Queue = asyncio.Queue()
    manager.add_queue(frontend_queue)

    prompt = [
        {"type": "text", "text": "Create a sunset image"},
        {"type": "image_mode", "image_mode": "generate"},
    ]

    settings = {
        "text": {"model": "gpt-4o-mini"},
        "image": {"model": "dall-e-3"},
    }

    with patch("features.chat.utils.generation_context.get_text_provider") as mock_text_provider, patch(
        "features.chat.utils.image_workflow.ImageService"
    ) as mock_image_service:
        # Use MagicMock with explicit async methods to avoid AsyncMock's
        # internal coroutine tracking issues that cause "never awaited" warnings
        mock_provider = MagicMock()
        mock_provider.get_model_config.return_value = None
        mock_provider.provider_name = "test"
        mock_provider.default_model = "gpt-4o-mini"

        async def mock_stream(*args, **kwargs):
            yield "A beautiful sunset"
            yield " over the ocean"

        mock_provider.stream = mock_stream
        mock_text_provider.return_value = mock_provider

        mock_img_service = MagicMock()
        generate_calls = []

        async def mock_generate(*args, **kwargs):
            generate_calls.append((args, kwargs))
            return {
                "image_url": "https://s3.amazonaws.com/test.png",
                "model": "dall-e-3",
                "settings": {},
            }

        mock_img_service.generate = mock_generate
        mock_image_service.return_value = mock_img_service

        result = await service.stream_response(
            prompt=prompt,
            settings=settings,
            customer_id=1,
            manager=manager,
        )

    await manager.signal_completion(token=completion_token)

    assert "image_data" in result
    assert result["image_data"]["image_url"] == "https://s3.amazonaws.com/test.png"

    text_chunks = []
    image_events = []
    while True:
        try:
            message = await asyncio.wait_for(frontend_queue.get(), timeout=1)
        except asyncio.TimeoutError:  # pragma: no cover - defensive guard against hangs
            pytest.fail("Timed out waiting for streaming manager to close queues")
        if message is None:
            break
        if message.get("type") == "text_chunk":
            text_chunks.append(message["content"])
        elif message.get("type") == "custom_event":
            image_events.append(message)

    assert "".join(text_chunks) == "A beautiful sunset over the ocean"
    assert any(
        event.get("content", {}).get("message") == "imageGenerated" for event in image_events
    )

    assert len(generate_calls) == 1, f"Expected 1 generate call, got {len(generate_calls)}"


async def test_stream_response_without_image_mode():
    """Should NOT trigger image generation without image_mode."""

    service = ChatService()
    manager = StreamingManager()
    completion_token = manager.create_completion_token()
    frontend_queue: asyncio.Queue = asyncio.Queue()
    manager.add_queue(frontend_queue)

    prompt = "Just a regular text prompt"
    settings = {"text": {"model": "gpt-4o-mini"}}

    with patch("features.chat.utils.generation_context.get_text_provider") as mock_text_provider, patch(
        "features.chat.utils.image_workflow.ImageService"
    ) as mock_image_service:
        # Use MagicMock with explicit async methods to avoid AsyncMock's
        # internal coroutine tracking issues that cause "never awaited" warnings
        mock_provider = MagicMock()
        mock_provider.get_model_config.return_value = None
        mock_provider.provider_name = "test"
        mock_provider.default_model = "gpt-4o-mini"

        async def mock_stream(*args, **kwargs):
            yield "Response"

        mock_provider.stream = mock_stream
        mock_text_provider.return_value = mock_provider

        mock_img_service = MagicMock()
        generate_calls = []

        async def mock_generate(*args, **kwargs):
            generate_calls.append((args, kwargs))
            return {}

        mock_img_service.generate = mock_generate
        mock_image_service.return_value = mock_img_service

        result = await service.stream_response(
            prompt=prompt,
            settings=settings,
            customer_id=1,
            manager=manager,
        )

    await manager.signal_completion(token=completion_token)

    assert "image_data" not in result
    assert len(generate_calls) == 0, f"Expected no generate calls, got {len(generate_calls)}"
