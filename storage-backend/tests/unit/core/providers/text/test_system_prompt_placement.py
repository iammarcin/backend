"""Live system prompt placement verification for provider SDKs.

These tests intentionally hit the real SDKs; avoid swapping in mocks or
we will miss regressions where the upstream APIs reject our payloads.
"""

from __future__ import annotations

from types import MethodType
from typing import Any

import pytest

from core.exceptions import ProviderError, RateLimitError
from core.providers.factory import get_text_provider
from tests.utils.live_providers import require_live_client, skip_if_transient_provider_error


def _get_usage_value(usage: object | None, attr: str, default: int = 0) -> int:
    """Safely extract integers from provider usage metadata."""

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


def _assert_text_or_reasoning(response: Any) -> None:
    """Accept either textual output or explicit reasoning content from Responses."""

    text_output = (response.text or "").strip()
    if text_output:
        return

    reasoning_output = (response.reasoning or "").strip() if response.reasoning else ""
    usage = (response.metadata or {}).get("usage") if response.metadata else None
    output_tokens = _get_usage_value(usage, "output_tokens")

    if reasoning_output:
        assert output_tokens > 0, "Expected token usage for reasoning-only responses."
        return

    assert output_tokens > 0, "Expected OpenAI Responses to provide text, reasoning, or token usage."


pytestmark = pytest.mark.live_api


@pytest.mark.anyio
async def test_anthropic_system_prompt_separate_parameter() -> None:
    """Anthropic should accept system prompts via the dedicated parameter."""

    require_live_client("anthropic_async", "ANTHROPIC_API_KEY")

    settings = {"text": {"model": "cheapest-claude"}}
    provider = get_text_provider(settings)

    try:
        response = await provider.generate(
            prompt="Say hello",
            system_prompt="You are a helpful assistant",
            temperature=0.1,
            max_tokens=64,
        )
    except (ProviderError, RateLimitError) as exc:  # pragma: no cover
        skip_if_transient_provider_error(exc, "Anthropic")
        raise

    assert response.text.strip()


@pytest.mark.anyio
async def test_openai_chat_system_prompt_in_messages() -> None:
    """Chat Completions should still accept system prompts in the messages list."""

    require_live_client("openai_async", "OPENAI_API_KEY")

    settings = {"text": {"model": "gpt-4o-mini"}}
    provider = get_text_provider(settings)

    try:
        response = await provider.generate(
            prompt="Hello",
            system_prompt="You are helpful",
            temperature=0.4,
            max_tokens=128,
        )
    except (ProviderError, RateLimitError) as exc:  # pragma: no cover
        skip_if_transient_provider_error(exc, "OpenAI")
        raise

    assert response.text.strip()


@pytest.mark.anyio
async def test_openai_responses_api_system_prompt() -> None:
    """Responses API models should still honour system prompts in the input array."""

    require_live_client("openai_async", "OPENAI_API_KEY")

    settings = {"text": {"model": "cheapest-openai"}}
    provider = get_text_provider(settings)
    model_name = provider.get_model_config().model_name

    try:
        response = await provider.generate(
            prompt="Give me one fact",
            system_prompt="Respond concisely",
            temperature=0.2,
            max_tokens=128,
            model=model_name,
        )
    except (ProviderError, RateLimitError) as exc:  # pragma: no cover
        skip_if_transient_provider_error(exc, "OpenAI")
        raise

    _assert_text_or_reasoning(response)


@pytest.mark.anyio
async def test_gemini_system_instruction_in_config(gemini_text_provider) -> None:
    """Gemini should surface system prompts through the config instruction."""

    require_live_client("gemini", "GOOGLE_API_KEY")

    provider = gemini_text_provider

    captured: dict[str, Any] = {}
    original_generate = provider._generate_async

    async def capture_generate(self, model: str, contents: list[Any], config: Any) -> Any:
        captured["model"] = model
        captured["contents"] = contents
        captured["config"] = config
        return await original_generate(model, contents, config)

    provider._generate_async = MethodType(capture_generate, provider)

    conversation = [
        {"role": "user", "content": "Outline a colour palette"},
    ]

    try:
        response = await provider.generate(
            prompt="Outline a colour palette",
            system_prompt="Be upbeat",
            temperature=0.5,
            max_tokens=128,
            messages=conversation,
        )
    except (ProviderError, RateLimitError) as exc:  # pragma: no cover
        skip_if_transient_provider_error(exc, "Gemini")
        raise

    assert response.text.strip()
    assert captured, "Gemini generate call arguments were not captured"
    assert captured["model"] == provider.get_model_config().model_name
    expected_texts = [item["content"] for item in conversation]

    captured_contents = captured["contents"]
    actual_texts: list[str] = []
    for entry in captured_contents:
        if isinstance(entry, str):
            actual_texts.append(entry)
            continue

        parts = getattr(entry, "parts", None)
        if parts:
            text_parts = [getattr(part, "text", "") for part in parts]
            actual_texts.append("".join(text_parts))
        else:
            actual_texts.append(getattr(entry, "text", ""))

    assert actual_texts == expected_texts
    first_entry = captured_contents[0]
    assert getattr(first_entry, "role", conversation[0]["role"]) == conversation[0]["role"]

    config = captured["config"]
    assert getattr(config, "system_instruction", None) == "Be upbeat"
    assert getattr(config, "temperature", None) == pytest.approx(0.5)


@pytest.mark.anyio
async def test_deepseek_system_prompt_in_messages() -> None:
    """DeepSeek should continue to require system prompts in the message list."""

    require_live_client("deepseek_async", "DEEPSEEK_API_KEY")

    settings = {"text": {"model": "deepseek"}}
    provider = get_text_provider(settings)

    try:
        response = await provider.generate(
            prompt="Provide a tip",
            system_prompt="You are an expert",
            temperature=0.3,
            max_tokens=128,
        )
    except (ProviderError, RateLimitError) as exc:  # pragma: no cover
        skip_if_transient_provider_error(exc, "DeepSeek")
        raise

    assert response.text.strip()


@pytest.mark.anyio
async def test_perplexity_no_system_prompt_parameter() -> None:
    """Perplexity should accept system prompts and return a valid response."""

    require_live_client("perplexity_async", "PERPLEXITY_API_KEY")

    settings = {"text": {"model": "cheapest-perplexity"}}
    provider = get_text_provider(settings)

    try:
        response = await provider.generate(
            prompt="Search for something",
            model="sonar",  # Explicitly use cheapest model
            system_prompt="Should be accepted now",
            temperature=0.2,
            max_tokens=256,
        )
    except (ProviderError, RateLimitError) as exc:  # pragma: no cover
        skip_if_transient_provider_error(exc, "Perplexity")
        raise

    assert response.text.strip()
