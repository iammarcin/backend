"""Live verification for important text-provider model aliases.

Do not replace these tests with mocked SDK calls—they are designed to
catch regressions in the request payloads that only surface against the
real provider APIs.
"""

from __future__ import annotations

from types import MethodType
from typing import Any

import pytest
from google.genai import types as genai_types

from core.exceptions import ProviderError, RateLimitError
from core.providers.factory import get_text_provider
from tests.utils.live_providers import require_live_client, skip_if_transient_provider_error


def _get_usage_value(usage: object | None, attr: str, default: int = 0) -> int:
    """Safely extract integers from usage metadata returned by providers."""

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
    """Accept responses that surface either final text or reasoning output."""

    text_output = (response.text or "").strip()
    if text_output:
        return

    reasoning_output = (response.reasoning or "").strip() if response.reasoning else ""
    usage = (response.metadata or {}).get("usage") if response.metadata else None
    output_tokens = _get_usage_value(usage, "output_tokens")

    if reasoning_output:
        assert output_tokens > 0, "Expected usage tokens for reasoning-only responses."
        return

    assert output_tokens > 0, "Expected textual or reasoning output from OpenAI Responses."


pytestmark = pytest.mark.live_api


async def _collect_stream_snippet(provider, **kwargs) -> str:
    """Collect a short snippet from a streaming response."""

    pieces: list[str] = []
    async for chunk in provider.stream(**kwargs):
        if chunk:
            if isinstance(chunk, str):
                pieces.append(chunk)
            elif isinstance(chunk, dict) and chunk.get("type") == "reasoning":
                pieces.append(chunk.get("content", ""))
            # Skip other dict types (like tool calls)
        if len("".join(pieces)) > 32:
            break
    return "".join(pieces)


@pytest.mark.anyio
async def test_cheapest_claude_stream_includes_system_prompt() -> None:
    """`cheapest-claude` should resolve to Haiku and support streaming with system prompts."""

    require_live_client("anthropic_async", "ANTHROPIC_API_KEY")

    provider = get_text_provider({"text": {"model": "cheapest-claude"}})
    assert provider.get_model_config().model_name == "claude-haiku-4-5"

    try:
        output = await _collect_stream_snippet(
            provider,
            prompt="List two colours",
            system_prompt="Respond cheerfully.",
            temperature=0.2,
            max_tokens=128,
        )
    except (ProviderError, RateLimitError) as exc:  # pragma: no cover - env dependent
        skip_if_transient_provider_error(exc, "Anthropic")
        raise
    except Exception as exc:  # pragma: no cover - defensive for Anthropic SDK errors
        if "overloaded" in str(exc).lower():
            pytest.skip(f"Anthropic service overloaded during test: {exc}")
        raise

    if not output.strip():
        pytest.skip("Anthropic stream returned no content (likely throttled)")


@pytest.mark.anyio
async def test_cheapest_openai_generate_uses_responses_format_with_system_prompt() -> None:
    """`cheapest-openai` should target the Responses API model and succeed with system prompts."""

    require_live_client("openai_async", "OPENAI_API_KEY")

    provider = get_text_provider({"text": {"model": "cheapest-openai"}})
    model_name = provider.get_model_config().model_name
    assert model_name == "gpt-5-nano"

    try:
        response = await provider.generate(
            prompt="Give me a fact about space",
            system_prompt="Keep it short",
            temperature=0.3,
            max_tokens=128,
            model=model_name,
        )
    except (ProviderError, RateLimitError) as exc:  # pragma: no cover - env dependent
        skip_if_transient_provider_error(exc, "OpenAI")
        raise

    _assert_text_or_reasoning(response)


@pytest.mark.anyio
async def test_cheapest_gemini_generate_sets_temperature_and_system_instruction(
    gemini_text_provider,
) -> None:
    """`cheapest-gemini` should resolve to Gemini Flash and accept system prompts."""

    require_live_client("gemini", "GOOGLE_API_KEY")

    provider = gemini_text_provider
    assert provider.get_model_config().model_name == "gemini-3-flash-preview"

    captured: dict[str, Any] = {}
    original_generate = provider._generate_async

    async def capture_generate(self, model: str, contents: list[Any], config: Any) -> Any:
        captured["model"] = model
        captured["contents"] = contents
        captured["config"] = config
        return await original_generate(model, contents, config)

    provider._generate_async = MethodType(capture_generate, provider)

    conversation = [
        {"role": "user", "content": "Our team meets monthly."},
        {"role": "assistant", "content": "Sounds fun!"},
        {"role": "user", "content": "Suggest a quick team icebreaker"},
    ]

    try:
        response = await provider.generate(
            prompt="Suggest a quick team icebreaker",
            system_prompt="Be playful",
            temperature=0.6,
            max_tokens=128,
            messages=conversation,
        )
    except (ProviderError, RateLimitError) as exc:  # pragma: no cover - env dependent
        skip_if_transient_provider_error(exc, "Gemini")
        raise

    assert response.text.strip()
    assert captured, "Gemini generate call arguments were not captured"
    assert captured["model"] == "gemini-3-flash-preview"
    actual_contents = captured["contents"]
    expected_strings = [item["content"] for item in conversation]
    assert len(actual_contents) == len(expected_strings)

    flattened: list[str] = []
    for content in actual_contents:
        if isinstance(content, genai_types.Content):
            parts = getattr(content, "parts", None) or []
            text_value = "".join(
                part.text for part in parts if getattr(part, "text", None)
            )
            flattened.append(text_value)
        else:
            flattened.append(str(content))

    assert flattened == expected_strings

    config = captured["config"]
    assert getattr(config, "system_instruction", None) == "Be playful"
    assert getattr(config, "temperature", None) == pytest.approx(0.6)


@pytest.mark.anyio
async def test_gpt4o_mini_stream_includes_system_prompt_and_temperature() -> None:
    """Ensure the `gpt-4o-mini` alias streams successfully with system prompts."""

    require_live_client("openai_async", "OPENAI_API_KEY")

    provider = get_text_provider({"text": {"model": "gpt-4o-mini"}})
    assert provider.get_model_config().model_name == "gpt-4o-mini"

    try:
        output = await _collect_stream_snippet(
            provider,
            prompt="Summarise why testing matters",
            system_prompt="You are an engineering coach",
            temperature=0.2,
            max_tokens=128,
        )
    except (ProviderError, RateLimitError) as exc:  # pragma: no cover - env dependent
        skip_if_transient_provider_error(exc, "OpenAI")
        raise

    assert output.strip()
