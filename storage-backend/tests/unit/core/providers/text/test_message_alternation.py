"""Live message alternation smoke tests for the provider SDKs.

These tests deliberately send edge-case chat histories to the real
providers.  If alternation logic regresses the upstream API should reject
the payload, which will fail the test.  Keep these calls live so we catch
format drift quickly.
"""

from __future__ import annotations

from typing import Any

import pytest

from core.exceptions import ProviderError, RateLimitError
from core.providers.factory import get_text_provider
from tests.utils.live_providers import require_live_client, skip_if_transient_provider_error

pytestmark = pytest.mark.live_api


@pytest.mark.anyio
async def test_anthropic_consecutive_user_messages_should_be_handled() -> None:
    """Anthropic should normalise repeated user turns before calling the API.

    The provider should handle consecutive user messages gracefully. Anthropic's
    API requires alternating roles, so the provider must normalize this.
    """

    require_live_client("anthropic_async", "ANTHROPIC_API_KEY")

    settings = {"text": {"model": "cheapest-claude"}}
    provider = get_text_provider(settings)

    # Construct messages with consecutive user turns (edge case)
    messages = [
        {"role": "user", "content": "Question one"},
        {"role": "user", "content": "Follow up without assistant"},
        {"role": "user", "content": "Final user turn"},
    ]

    try:
        response = await provider.generate(
            prompt="Final user turn",
            system_prompt="Answer briefly.",
            messages=messages,
            max_tokens=64,
        )
    except (ProviderError, RateLimitError) as exc:  # pragma: no cover - env specific
        skip_if_transient_provider_error(exc, "Anthropic")
        raise

    assert response.text.strip()


@pytest.mark.anyio
async def test_deepseek_consecutive_assistant_messages() -> None:
    """DeepSeek requires strict alternation; we validate our normalisation.

    The provider should normalize consecutive assistant messages to meet
    DeepSeek's strict alternation requirement.
    """

    require_live_client("deepseek_async", "DEEPSEEK_API_KEY")

    settings = {"text": {"model": "deepseek"}}
    provider = get_text_provider(settings)

    # Construct messages with consecutive assistant turns (edge case)
    messages: list[dict[str, Any]] = [
        {"role": "assistant", "content": "Intro"},
        {"role": "assistant", "content": "Second assistant turn"},
        {"role": "user", "content": "User asks a new thing"},
    ]

    try:
        response = await provider.generate(
            prompt="User asks a new thing",
            system_prompt="Stay concise.",
            messages=messages,
            max_tokens=64,
        )
    except (ProviderError, RateLimitError) as exc:  # pragma: no cover - env specific
        skip_if_transient_provider_error(exc, "DeepSeek")
        raise

    assert response.text.strip()


@pytest.mark.anyio
async def test_openai_accepts_non_alternating_messages() -> None:
    """OpenAI should still accept duplicate roles without preprocessing.

    OpenAI's API is more flexible and can handle non-alternating messages.
    """

    require_live_client("openai_async", "OPENAI_API_KEY")

    settings = {"text": {"model": "gpt-4o-mini"}}
    provider = get_text_provider(settings)

    # Construct messages with consecutive assistant turns
    messages = [
        {"role": "assistant", "content": "Sure"},
        {"role": "assistant", "content": "Here's more"},
        {"role": "user", "content": "User finishes"},
    ]

    try:
        response = await provider.generate(
            prompt="User finishes", system_prompt="Reply helpfully", messages=messages
        )
    except (ProviderError, RateLimitError) as exc:  # pragma: no cover - env specific
        skip_if_transient_provider_error(exc, "OpenAI")
        raise

    assert response.text.strip()


@pytest.mark.anyio
async def test_gemini_accepts_non_standard_order(gemini_text_provider) -> None:
    """Gemini should continue to accept out-of-order messages after conversion."""

    require_live_client("gemini", "GOOGLE_API_KEY")

    provider = gemini_text_provider

    # Construct messages preserving the non-standard ordering
    messages = [
        {"role": "assistant", "content": "Response"},
        {"role": "user", "content": "But what about X?"},
        {"role": "assistant", "content": "Another answer"},
        {"role": "user", "content": "Final clarification"},
    ]

    try:
        response = await provider.generate(
            prompt="Final clarification",
            system_prompt="Respond as a product expert.",
            messages=messages,
            max_tokens=64,
        )
    except (ProviderError, RateLimitError) as exc:  # pragma: no cover - env specific
        skip_if_transient_provider_error(exc, "Gemini")
        raise

    assert response.text.strip()
