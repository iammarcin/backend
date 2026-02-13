"""Integration tests for batch-enabled text providers (real APIs)."""

from __future__ import annotations

import os

import pytest

from core.providers.text.anthropic import AnthropicTextProvider
from core.providers.text.gemini import GeminiTextProvider
from core.providers.text.openai import OpenAITextProvider
from tests.utils.live_providers import require_live_client


@pytest.mark.batch
@pytest.mark.batch_integration
@pytest.mark.live_api
@pytest.mark.skipif(
    os.getenv("RUN_MANUAL_TESTS") != "1",
    reason="Live API test - set RUN_MANUAL_TESTS=1 to run",
)
@pytest.mark.asyncio
async def test_openai_batch_integration():
    require_live_client("openai_async", "OPENAI_API_KEY")

    provider = OpenAITextProvider()
    requests = [
        {"custom_id": "batch-int-1", "prompt": "Reply with the word HELLO", "max_tokens": 10},
        {"custom_id": "batch-int-2", "prompt": "Reply with the word WORLD", "max_tokens": 10},
    ]

    responses = await provider.generate_batch(requests)
    assert len(responses) == 2
    assert responses[0].custom_id == "batch-int-1"
    assert responses[1].custom_id == "batch-int-2"


@pytest.mark.batch
@pytest.mark.batch_integration
@pytest.mark.live_api
@pytest.mark.skipif(
    os.getenv("RUN_MANUAL_TESTS") != "1",
    reason="Live API test - set RUN_MANUAL_TESTS=1 to run",
)
@pytest.mark.asyncio
async def test_anthropic_batch_integration():
    require_live_client("anthropic_async", "ANTHROPIC_API_KEY")

    provider = AnthropicTextProvider()
    requests = [
        {"custom_id": "claude-int-1", "prompt": "Say hi in one word", "max_tokens": 10},
        {"custom_id": "claude-int-2", "prompt": "Say bye in one word", "max_tokens": 10},
    ]

    responses = await provider.generate_batch(requests)
    assert len(responses) == 2
    assert responses[0].custom_id == "claude-int-1"
    assert responses[1].custom_id == "claude-int-2"


@pytest.mark.batch
@pytest.mark.batch_integration
@pytest.mark.live_api
@pytest.mark.skipif(
    os.getenv("RUN_MANUAL_TESTS") != "1",
    reason="Live API test - set RUN_MANUAL_TESTS=1 to run",
)
@pytest.mark.asyncio
async def test_gemini_batch_integration():
    require_live_client("gemini", "GOOGLE_API_KEY")

    provider = GeminiTextProvider()
    requests = [
        {"custom_id": "gemini-int-1", "prompt": "Respond with ALOHA", "max_tokens": 10},
        {"custom_id": "gemini-int-2", "prompt": "Respond with MAHALO", "max_tokens": 10},
    ]

    responses = await provider.generate_batch(requests)
    assert len(responses) == 2
    assert responses[0].custom_id == "gemini-int-1"
    assert responses[1].custom_id == "gemini-int-2"
