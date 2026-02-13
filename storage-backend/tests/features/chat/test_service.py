"""Tests for the chat service error propagation."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from core.exceptions import ValidationError
from features.chat.service import ChatService


def test_generate_response_propagates_validation_error() -> None:
    """ChatService.generate_response should surface validation errors."""

    service = ChatService()
    context = SimpleNamespace(text_prompt="Hello", image_mode=None, input_image_url=None)

    with patch("features.chat.service.parse_prompt", return_value=context), patch(
        "features.chat.service.resolve_generation_context"
    ) as mock_resolve:
        provider = SimpleNamespace(
            generate=AsyncMock(side_effect=ValidationError("Unsupported option", field="chat.prompt"))
        )
        mock_resolve.return_value = (provider, "gpt-4o", 0.8, 2048)

        async def _run() -> None:
            await service.generate_response(
                prompt="Hello",
                settings={},
                customer_id=1,
            )

        with pytest.raises(ValidationError) as exc_info:
            asyncio.run(_run())

    assert "Unsupported option" in str(exc_info.value)


def test_stream_response_chunks_propagates_validation_error() -> None:
    """ChatService.stream_response_chunks should re-raise validation failures."""

    service = ChatService()
    context = SimpleNamespace(text_prompt="World", image_mode=None, input_image_url=None)

    with patch("features.chat.service.parse_prompt", return_value=context), patch(
        "features.chat.service.resolve_generation_context"
    ) as mock_resolve:
        def failing_stream(*args, **kwargs):
            class _Iterator:
                def __aiter__(self_inner):
                    return self_inner

                async def __anext__(self_inner):
                    raise ValidationError("Bad stream request", field="chat.prompt")

            return _Iterator()

        provider = SimpleNamespace(stream=failing_stream)
        mock_resolve.return_value = (provider, "gpt-4o", 0.7, 1024)

        async def _run() -> None:
            async for _chunk in service.stream_response_chunks(
                prompt="World",
                settings={},
                customer_id=1,
            ):
                pass

        with pytest.raises(ValidationError) as exc_info:
            asyncio.run(_run())

    assert "Bad stream request" in str(exc_info.value)
