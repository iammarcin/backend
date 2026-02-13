"""Test that provider kwargs are properly filtered before API calls.

This test ensures that workflow-specific kwargs (settings, manager, etc.)
are stripped out before being passed to the underlying AI SDKs, preventing
"unexpected keyword argument" errors.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from core.providers.factory import get_text_provider


@pytest.mark.anyio
async def test_deepseek_stream_filters_settings_kwarg() -> None:
    """DeepSeek stream should filter out 'settings' kwarg before API call."""
    settings = {"text": {"model": "deepseek-chat"}}
    provider = get_text_provider(settings)

    # Mock the client's chat.completions.create to verify kwargs
    with patch.object(provider.client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
        # Configure mock to return a valid stream response
        class MockDelta:
            content = "response"

        class MockChoice:
            delta = MockDelta()

        class MockChunk:
            choices = [MockChoice()]

        async def stream_generator(**kwargs):
            yield MockChunk()

        mock_create.side_effect = stream_generator

        # Call stream with workflow kwargs (settings, manager, etc.)
        chunks = []
        async for chunk in provider.stream(
            prompt="Test prompt",
            system_prompt="Test system",
            temperature=0.1,
            max_tokens=256,
            # These should all be filtered out before reaching the API
            settings={"general": {"ai_agent_enabled": True}},
            manager=None,
        ):
            chunks.append(chunk)

        # Verify the API was called without these kwargs
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]

        assert "settings" not in call_kwargs, "settings kwarg should be filtered before API call"
        assert "manager" not in call_kwargs, "manager kwarg should be filtered before API call"
        assert call_kwargs["model"] == "deepseek-chat"
        assert call_kwargs["stream"] is True
        assert "messages" in call_kwargs


@pytest.mark.anyio
async def test_deepseek_generate_filters_settings_kwarg() -> None:
    """DeepSeek generate should filter out 'settings' kwarg before API call."""
    settings = {"text": {"model": "deepseek-chat"}}
    provider = get_text_provider(settings)

    # Mock the client's chat.completions.create
    with patch.object(provider.client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
        # Configure mock to return a valid response
        class MockUsage:
            prompt_tokens = 10
            completion_tokens = 20

            def model_dump(self):
                return {"prompt_tokens": self.prompt_tokens, "completion_tokens": self.completion_tokens}

        class MockMessage:
            content = "response"

        class MockChoice:
            finish_reason = "stop"
            message = MockMessage()

        class MockResponse:
            choices = [MockChoice()]
            usage = MockUsage()

        mock_create.return_value = MockResponse()

        # Call generate with workflow kwargs
        response = await provider.generate(
            prompt="Test prompt",
            system_prompt="Test system",
            temperature=0.1,
            max_tokens=256,
            # These should all be filtered out before reaching the API
            settings={"general": {"ai_agent_enabled": True}},
            manager=None,
        )

        # Verify the API was called without these kwargs
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]

        assert "settings" not in call_kwargs, "settings kwarg should be filtered before API call"
        assert "manager" not in call_kwargs, "manager kwarg should be filtered before API call"
        assert call_kwargs["model"] == "deepseek-chat"
        assert "messages" in call_kwargs
        assert response.text == "response"


@pytest.mark.anyio
async def test_perplexity_stream_filters_settings_kwarg() -> None:
    """Perplexity stream should filter out 'settings' kwarg before API call."""
    settings = {"text": {"model": "perplexity"}}
    provider = get_text_provider(settings)

    # Mock the client's chat.completions.create to verify kwargs
    with patch.object(provider.client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
        # Configure mock to return a valid stream response
        class MockDelta:
            content = "response"

        class MockChoice:
            delta = MockDelta()

        class MockChunk:
            choices = [MockChoice()]

        async def stream_generator(**kwargs):
            yield MockChunk()

        mock_create.side_effect = stream_generator

        # Call stream with workflow kwargs
        chunks = []
        async for chunk in provider.stream(
            prompt="Test prompt",
            temperature=0.1,
            max_tokens=256,
            settings={"general": {"ai_agent_enabled": True}},
            manager=None,
        ):
            chunks.append(chunk)

        # Verify the API was called without these kwargs
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]

        assert "settings" not in call_kwargs, "settings kwarg should be filtered before API call"
        assert "manager" not in call_kwargs, "manager kwarg should be filtered before API call"
        assert call_kwargs["stream"] is True
        assert "messages" in call_kwargs
