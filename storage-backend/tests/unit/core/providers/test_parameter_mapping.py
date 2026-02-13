"""Unit tests for provider parameter mapping and reasoning settings."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.providers.registry.model_config import ModelConfig
from core.providers.text.anthropic import AnthropicTextProvider
from core.providers.text.openai import OpenAITextProvider
from core.providers.text.openai_batch import prepare_openai_batch_requests


pytestmark = pytest.mark.anyio("asyncio")


class TestAnthropicParameters:
    """Validate Anthropic parameter handling."""

    @pytest.fixture()
    def provider(self) -> AnthropicTextProvider:
        with patch("core.providers.text.anthropic.ai_clients") as mock_clients:
            client = MagicMock()
            client.messages.create = AsyncMock(
                return_value=MagicMock(
                    content=[MagicMock(text="Test response", type="text")]
                )
            )
            mock_clients.get.return_value = client
            provider = AnthropicTextProvider()
        return provider

    @pytest.mark.asyncio
    async def test_system_prompt_sent_as_separate_parameter(
        self, provider: AnthropicTextProvider
    ) -> None:
        """System prompts should be passed via the dedicated ``system`` field."""

        await provider.generate(prompt="Hello", system_prompt="You are helpful")

        call_kwargs = provider.client.messages.create.call_args.kwargs
        assert call_kwargs["system"] == "You are helpful"
        assert all(msg.get("role") != "system" for msg in call_kwargs["messages"])

    @pytest.mark.asyncio
    async def test_thinking_budget_parameter(self, provider: AnthropicTextProvider) -> None:
        """Thinking mode should include the requested token budget."""

        await provider.generate(
            prompt="Complex task",
            enable_reasoning=True,
            reasoning_value=2048,
        )

        call_kwargs = provider.client.messages.create.call_args.kwargs
        thinking = call_kwargs["thinking"]
        assert thinking["type"] == "enabled"
        assert thinking["budget_tokens"] == 2048


class TestOpenAIParameters:
    """Validate OpenAI parameter translation."""

    @pytest.fixture()
    def provider(self) -> OpenAITextProvider:
        with patch("core.providers.text.openai.ai_clients") as mock_clients:
            client = MagicMock()
            message = MagicMock(content="ok", reasoning_content=None)
            client.chat.completions.create = AsyncMock(
                return_value=MagicMock(
                    choices=[MagicMock(message=message, finish_reason="stop")],
                    usage=MagicMock(model_dump=lambda: {"total_tokens": 10}),
                )
            )
            mock_clients.get.return_value = client
            provider = OpenAITextProvider()
        return provider

    def _set_model_config(self, provider: OpenAITextProvider, **overrides: Any) -> None:
        config = ModelConfig(
            model_name=overrides.get("model_name", "gpt-4o-mini"),
            provider_name="openai",
            api_type=overrides.get("api_type", "chat_completion"),
            is_reasoning_model=overrides.get("is_reasoning_model", False),
            supports_reasoning_effort=overrides.get("supports_reasoning_effort", False),
            reasoning_effort_values=overrides.get(
                "reasoning_effort_values",
                ["low", "medium", "high"],
            ),
        )
        provider.set_model_config(config)

    @pytest.mark.asyncio
    async def test_standard_model_uses_max_tokens(
        self, provider: OpenAITextProvider
    ) -> None:
        """Non reasoning models should rely on ``max_tokens``."""

        self._set_model_config(provider)
        await provider.generate(prompt="Hi", model="gpt-4o-mini", max_tokens=500)

        call_kwargs = provider.client.chat.completions.create.call_args.kwargs
        assert call_kwargs["max_tokens"] == 500
        assert "max_completion_tokens" not in call_kwargs

    @pytest.mark.asyncio
    async def test_reasoning_model_uses_max_completion_tokens(
        self, provider: OpenAITextProvider
    ) -> None:
        """Reasoning models should translate max tokens to completion tokens."""

        self._set_model_config(
            provider,
            model_name="gpt-5-mini",
            is_reasoning_model=True,
            supports_reasoning_effort=True,
        )

        await provider.generate(
            prompt="Solve this",
            model="gpt-5-mini",
            max_tokens=1200,
            enable_reasoning=True,
            reasoning_value="medium",
        )

        call_kwargs = provider.client.chat.completions.create.call_args.kwargs
        assert call_kwargs["max_completion_tokens"] == 1200
        assert call_kwargs["reasoning_effort"] == "medium"
        assert "max_tokens" not in call_kwargs

    def test_batch_standard_model_uses_max_tokens(self, provider: OpenAITextProvider) -> None:
        """Batch requests should send ``max_tokens`` for non-reasoning models."""

        self._set_model_config(provider)
        requests = [
            {
                "custom_id": "req-1",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 256,
            }
        ]

        batch_requests, _ = prepare_openai_batch_requests(provider, requests)
        body = batch_requests[0]["body"]
        assert body["max_tokens"] == 256
        assert "max_completion_tokens" not in body

    def test_batch_reasoning_models_use_max_completion_tokens(
        self, provider: OpenAITextProvider
    ) -> None:
        """Batch requests should translate token params for reasoning models."""

        self._set_model_config(
            provider,
            model_name="o1-preview",
            is_reasoning_model=True,
        )
        requests = [
            {
                "custom_id": "req-1",
                "messages": [{"role": "user", "content": "Solve"}],
                "model": "o1-preview",
                "max_tokens": 512,
            }
        ]

        batch_requests, _ = prepare_openai_batch_requests(provider, requests)
        body = batch_requests[0]["body"]
        assert body["max_completion_tokens"] == 512
        assert "max_tokens" not in body
