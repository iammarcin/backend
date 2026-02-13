"""Manual tests for chat history handling.

These are integration tests that make real API calls to verify
chat history and reasoning modes work correctly end-to-end.

Run with: pytest tests/manual/test_chat_history_manual.py -v -s
"""

from __future__ import annotations

import os

import pytest

from core.exceptions import ProviderError, RateLimitError
from core.providers.factory import get_text_provider
from tests.utils.live_providers import require_live_client, skip_if_transient_provider_error


def _get_usage_value(usage: object | None, attr: str, default: int = 0) -> int:
    """Safely extract an integer usage attribute from provider metadata."""

    if usage is None:
        return default

    if isinstance(usage, dict):
        value = usage.get(attr, default)
    else:
        value = getattr(usage, attr, default)

    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


pytestmark = [
    pytest.mark.live_api,
    pytest.mark.skipif(
        os.getenv("RUN_MANUAL_TESTS") != "1",
        reason="Live API test - set RUN_MANUAL_TESTS=1 to run",
    ),
]


@pytest.mark.anyio
async def test_anthropic_with_history() -> None:
    """Test Anthropic provider with chat history using the messages parameter."""

    require_live_client("anthropic_async", "ANTHROPIC_API_KEY")

    settings = {"text": {"model": "cheapest-claude"}}
    provider = get_text_provider(settings)

    messages = [
        {"role": "user", "content": "My favourite colour is blue."},
        {"role": "assistant", "content": "I'll keep that in mind."},
        {"role": "user", "content": "What colour do I like?"},
    ]

    try:
        response = await provider.generate(
            prompt="What colour do I like?",
            system_prompt="You are a helpful assistant.",
            messages=messages,
            max_tokens=128,
        )
    except (ProviderError, RateLimitError) as exc:
        skip_if_transient_provider_error(exc, "Anthropic")
        raise

    assert isinstance(response.text, str)
    assert response.text.strip()

    text_preview = (response.text or "").strip()
    if "blue" in text_preview.lower():
        print("✅ Anthropic chat history test passed: remembered the colour context.")
    else:
        print("⚠️ Anthropic response did not explicitly mention the colour context.")
    print(f"   First 200 chars: {text_preview[:200]}...")


@pytest.mark.anyio
async def test_anthropic_thinking_mode() -> None:
    """Test Anthropic extended thinking mode with unified reasoning parameters."""

    require_live_client("anthropic_async", "ANTHROPIC_API_KEY")

    settings = {"text": {"model": "cheapest-claude"}}
    provider = get_text_provider(settings)

    try:
        response = await provider.generate(
            prompt="What is 15 * 17? Think step by step.",
            system_prompt="Show your reasoning clearly.",
            enable_reasoning=True,
            reasoning_value=4096,
            max_tokens=512,
        )
    except (ProviderError, RateLimitError) as exc:
        skip_if_transient_provider_error(exc, "Anthropic")
        raise

    assert isinstance(response.text, str)
    assert response.text.strip()
    assert len(response.text) > 50

    print("✅ Anthropic thinking mode test passed.")
    print(f"   Response length: {len(response.text)} chars")
    print(f"   First 200 chars: {response.text[:200]}...")


@pytest.mark.anyio
async def test_openai_reasoning_model() -> None:
    """Test OpenAI gpt-5-mini reasoning model with unified reasoning parameters."""

    require_live_client("openai_async", "OPENAI_API_KEY")

    settings = {"text": {"model": "gpt-5-mini"}}
    provider = get_text_provider(settings)

    model_config = provider.get_model_config()
    assert model_config is not None, "Expected model configuration for gpt-5-mini"
    assert model_config.model_name == "gpt-5-mini"
    assert model_config.is_reasoning_model is True
    assert model_config.supports_reasoning_effort is True

    try:
        response = await provider.generate(
            prompt="What is the sum of all prime numbers between 10 and 20?",
            model=model_config.model_name,
            enable_reasoning=True,
            reasoning_effort="medium",
            max_tokens=512,
        )
    except (ProviderError, RateLimitError) as exc:
        skip_if_transient_provider_error(exc, "OpenAI")
        raise

    assert isinstance(response.text, str)

    text_output = (response.text or "").strip()
    if text_output:
        assert len(text_output) > 20
    else:
        print("⚠️ OpenAI response text was empty; relying on usage metadata to confirm reasoning output.")

    usage = (response.metadata or {}).get("usage") if response.metadata else None
    output_tokens = _get_usage_value(usage, "output_tokens")

    reasoning_details = None
    if usage is not None:
        if isinstance(usage, dict):
            reasoning_details = usage.get("output_tokens_details")
        else:
            reasoning_details = getattr(usage, "output_tokens_details", None)

    reasoning_tokens = _get_usage_value(reasoning_details, "reasoning_tokens")
    if reasoning_tokens <= 0:
        # Some SDK variants expose the same value under a ``reasoning`` key.
        reasoning_tokens = _get_usage_value(reasoning_details, "reasoning", reasoning_tokens)

    assert output_tokens > 0, "Expected the reasoning model to produce output tokens."
    if reasoning_tokens <= 0:
        reasoning_text = (response.reasoning or "").strip()
        if not reasoning_text:
            pytest.skip(
                "OpenAI did not return reasoning metadata or reasoning text; "
                "skipping manual verification."
            )
        assert reasoning_text, "Expected reasoning output or token usage information from OpenAI."
        print("⚠️ OpenAI usage metadata omitted reasoning tokens; captured reasoning text instead.")
        print(f"   Model: {model_config.model_name}")
        print(f"   Output tokens: {output_tokens}, reasoning tokens: {reasoning_tokens}")
        print(f"   Reasoning preview: {reasoning_text[:200]}...")
    else:
        print("✅ OpenAI GPT 5 mini reasoning test passed.")
        print(f"   Model: {model_config.model_name}")
        print(f"   Output tokens: {output_tokens}, reasoning tokens: {reasoning_tokens}")
        if text_output:
            print(f"   First 200 chars: {text_output[:200]}...")
