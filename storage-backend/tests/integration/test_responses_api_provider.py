"""Integration-style tests for the OpenAI Responses API adapter."""

from __future__ import annotations

import asyncio
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.providers.capabilities import ProviderCapabilities
from core.providers.text.openai import OpenAITextProvider
from core.providers.registry.model_config import ModelConfig


@pytest.fixture
def responses_api_provider() -> OpenAITextProvider:
    """Create a provider configured for Responses API usage."""

    provider = OpenAITextProvider.__new__(OpenAITextProvider)
    provider.capabilities = ProviderCapabilities(
        streaming=True,
        reasoning=False,
        citations=False,
        audio_input=False,
        image_input=True,
    )
    provider.client = MagicMock()
    provider.client.responses = MagicMock()

    config = ModelConfig(
        model_name="gpt-5-mini",
        provider_name="openai",
        api_type="responses_api",
        is_reasoning_model=True,
        support_image_input=True,
        supports_reasoning_effort=True,
        supports_temperature=False,
        reasoning_effort_values=["low", "medium", "high"],
    )
    provider.set_model_config(config)

    return provider


def test_generate_uses_responses_api(responses_api_provider: OpenAITextProvider) -> None:
    """Ensure generate() delegates to the Responses API client."""

    mock_response = MagicMock()
    mock_output_item = MagicMock()
    mock_output_item.type = "text"
    mock_output_item.text = "Test response"
    mock_response.output = [mock_output_item]
    responses_api_provider.client.responses.create = AsyncMock(return_value=mock_response)

    result = asyncio.run(
        responses_api_provider.generate(
            prompt="Hello",
            model="gpt-5-mini",
        )
    )

    responses_api_provider.client.responses.create.assert_called_once()
    assert result.text == "Test response"


def test_stream_uses_responses_api(responses_api_provider: OpenAITextProvider) -> None:
    """Ensure stream() yields chunks from the Responses API."""

    mock_event1 = MagicMock()
    mock_event1.type = "response.text.delta"
    mock_event1.delta = "Hello"

    mock_event2 = MagicMock()
    mock_event2.type = "response.text.delta"
    mock_event2.delta = " world"

    mock_event3 = MagicMock()
    mock_event3.type = "response.completed"

    async def mock_stream() -> AsyncIterator[MagicMock]:
        yield mock_event1
        yield mock_event2
        yield mock_event3

    responses_api_provider.client.responses.create = AsyncMock(return_value=mock_stream())

    async def collect() -> list[str]:
        chunks: list[str] = []
        async for chunk in responses_api_provider.stream(prompt="Hello", model="gpt-5-mini"):
            chunks.append(chunk)
        return chunks

    chunks = asyncio.run(collect())

    responses_api_provider.client.responses.create.assert_called_once()
    assert chunks == ["Hello", " world"]
