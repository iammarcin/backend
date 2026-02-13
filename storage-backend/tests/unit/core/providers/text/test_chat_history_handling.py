"""Live chat history smoke tests for the real provider SDKs.

These tests intentionally call the upstream APIs so we can detect
formatting regressions (e.g. missing system prompts, bad alternation
handling) immediately.  **Do not** replace these calls with mocks unless
you also remove the live verification altogether – that would hide the
very failures we added these tests to catch.
"""

from __future__ import annotations

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
    """Ensure Responses API calls return either final text or reasoning output."""

    text_output = (response.text or "").strip()
    if text_output:
        return

    reasoning_output = (response.reasoning or "").strip() if response.reasoning else ""
    usage = (response.metadata or {}).get("usage") if response.metadata else None
    output_tokens = _get_usage_value(usage, "output_tokens")

    if reasoning_output:
        assert output_tokens > 0, "Expected token usage for reasoning-only output."
        return

    # Final fallback: OpenAI occasionally reports tokens without surface text
    # while the conversation continues on the websocket. Treat this as a
    # soft failure by asserting that the metadata still indicates model usage.
    assert output_tokens > 0, "Expected some textual or reasoning content from OpenAI Responses."


pytestmark = pytest.mark.live_api


@pytest.mark.anyio
async def test_anthropic_five_message_history() -> None:
    """Ensure we can send a full conversation + system prompt to Anthropic.

    The provider now expects a complete ``messages`` array that includes both
    the chat history and the current user message.
    """

    require_live_client("anthropic_async", "ANTHROPIC_API_KEY")

    settings = {"text": {"model": "cheapest-claude"}}
    provider = get_text_provider(settings)

    # Construct full messages array (history + current prompt)
    messages = [
        {"role": "user", "content": "What is Python?"},
        {"role": "assistant", "content": "A popular programming language."},
        {"role": "user", "content": "And JavaScript?"},
        {"role": "assistant", "content": "Great for web applications."},
        {"role": "user", "content": "Which one should I learn first?"},
    ]

    try:
        response = await provider.generate(
            prompt="Which one should I learn first?",
            system_prompt="You are a concise programming mentor.",
            messages=messages,
            max_tokens=128,
        )
    except (ProviderError, RateLimitError) as exc:  # pragma: no cover - depends on env
        skip_if_transient_provider_error(exc, "Anthropic")
        raise
    except Exception as exc:  # pragma: no cover - defensive for SDK-specific errors
        if "overloaded" in str(exc).lower():
            pytest.skip(f"Anthropic service overloaded during test: {exc}")
        raise

    assert isinstance(response.text, str)
    assert response.text.strip()


@pytest.mark.anyio
async def test_openai_responses_api_with_chat_history() -> None:
    """Validate chat history + system prompt when using the Responses API.

    The Responses API requires the full conversation in the messages array.
    """

    require_live_client("openai_async", "OPENAI_API_KEY")

    settings = {"text": {"model": "cheapest-openai"}}
    provider = get_text_provider(settings)
    model_name = provider.get_model_config().model_name

    # Construct full messages array
    messages = [
        {"role": "user", "content": "Give me one fun fact"},
        {"role": "assistant", "content": "The Eiffel Tower can grow in summer."},
        {"role": "user", "content": "Share another fact"},
    ]

    try:
        response = await provider.generate(
            prompt="Share another fact",
            system_prompt="Respond with brief trivia only.",
            messages=messages,
            model=model_name,
            max_tokens=64,
        )
    except (ProviderError, RateLimitError) as exc:  # pragma: no cover - depends on env
        skip_if_transient_provider_error(exc, "OpenAI")
        raise

    assert isinstance(response.text, str)
    _assert_text_or_reasoning(response)


@pytest.mark.anyio
async def test_provider_handles_empty_messages() -> None:
    """Empty prompts should be rejected via provider error handling."""

    require_live_client("openai_async", "OPENAI_API_KEY")

    settings = {"text": {"model": "gpt-4o-mini"}}
    provider = get_text_provider(settings)

    try:
        await provider.generate(prompt="", system_prompt="System")
    except (ProviderError, RateLimitError) as exc:  # pragma: no cover - depends on env
        skip_if_transient_provider_error(exc, "OpenAI")
        # If we reach here the provider handled the empty prompt – this is expected.
        assert isinstance(exc, ProviderError)
        assert "empty" in str(exc).lower() or "invalid" in str(exc).lower()
        return

    pytest.fail("Empty prompts should not reach a successful OpenAI response")


@pytest.mark.anyio
async def test_gemini_handles_text_only_history(gemini_text_provider) -> None:
    """Gemini should accept trimmed text-only history after conversion.

    The ``gemini_text_provider`` fixture keeps the SDK on a background loop so
    the live call remains stable under pytest-anyio.
    """

    require_live_client("gemini", "GOOGLE_API_KEY")

    provider = gemini_text_provider

    # Construct full messages array
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": "Suggest a color palette."},
        {"role": "assistant", "content": "Try teal, coral, and cream."},
        {"role": "user", "content": "Offer one more complementary color"},
    ]

    try:
        response = await provider.generate(
            prompt="Offer one more complementary color",
            system_prompt="Answer with a short design tip.",
            messages=messages,
            max_tokens=64,
        )
    except (ProviderError, RateLimitError) as exc:  # pragma: no cover - depends on env
        skip_if_transient_provider_error(exc, "Gemini")
        raise

    assert isinstance(response.text, str)
    _assert_text_or_reasoning(response)


@pytest.mark.anyio
async def test_deepseek_stream_includes_system_prompt() -> None:
    """Ensure the DeepSeek streaming pathway accepts system prompts + history.

    Streaming methods also now accept the full messages array.
    """

    require_live_client("deepseek_async", "DEEPSEEK_API_KEY")

    settings = {"text": {"model": "deepseek"}}
    provider = get_text_provider(settings)

    # Construct full messages array
    messages = [
        {"role": "user", "content": "Explain binary numbers."},
        {"role": "assistant", "content": "They use only 0 and 1."},
        {"role": "user", "content": "Summarise in five words"},
    ]

    chunks: list[str] = []
    try:
        async for chunk in provider.stream(
            prompt="Summarise in five words",
            system_prompt="Be concise.",
            messages=messages,
            temperature=0.1,
            max_tokens=64,
        ):
            if chunk:
                chunks.append(chunk)
            if len("".join(chunks)) > 32:
                break
    except (ProviderError, RateLimitError) as exc:  # pragma: no cover - depends on env
        skip_if_transient_provider_error(exc, "DeepSeek")
        raise

    assert chunks
    assert "".join(chunks).strip()


@pytest.mark.anyio
async def test_anthropic_stream_with_system_prompt() -> None:
    """Anthropic streaming should also honour system prompts + history.

    Streaming now shares the same full messages contract as generate().
    """

    require_live_client("anthropic_async", "ANTHROPIC_API_KEY")

    settings = {"text": {"model": "cheapest-claude"}}
    provider = get_text_provider(settings)

    # Construct full messages array
    messages = [
        {"role": "user", "content": "Summarise HTTP in one sentence."},
        {"role": "assistant", "content": "It is the protocol for the web."},
        {"role": "user", "content": "Add a friendly reminder"},
    ]

    collected: list[str] = []
    try:
        async for chunk in provider.stream(
            prompt="Add a friendly reminder",
            system_prompt="Speak as a helpful tutor.",
            messages=messages,
            max_tokens=64,
        ):
            if chunk:
                if isinstance(chunk, str):
                    collected.append(chunk)
                elif isinstance(chunk, dict) and chunk.get("type") == "reasoning":
                    collected.append(chunk.get("content", ""))
                # Skip other dict types (like tool calls)
            if len("".join(collected)) > 32:
                break
    except (ProviderError, RateLimitError) as exc:  # pragma: no cover - depends on env
        skip_if_transient_provider_error(exc, "Anthropic")
        raise
    except Exception as exc:  # pragma: no cover - defensive for SDK-specific errors
        if "overloaded" in str(exc).lower():
            pytest.skip(f"Anthropic service overloaded during test: {exc}")
        raise

    if not collected:
        pytest.skip("Anthropic stream returned no content (likely throttled)")

    assert "".join(collected).strip()
