"""Integration-style tests verifying chat history flows through chat service."""

from __future__ import annotations

from typing import AsyncIterator, ClassVar, List
from unittest.mock import MagicMock

import pytest

from core.providers.base import BaseTextProvider
from core.providers.capabilities import ProviderCapabilities
from core.providers.factory import register_text_provider
from core.pydantic_schemas import ProviderResponse
from features.chat.services.streaming.service import ChatService


pytestmark = pytest.mark.anyio("asyncio")


class HistoryTrackingProvider(BaseTextProvider):
    """Stub provider capturing the messages passed for generation."""

    last_instance: ClassVar["HistoryTrackingProvider" | None] = None

    def __init__(self) -> None:
        self.capabilities = ProviderCapabilities(streaming=True)
        self.received_messages: List[dict] | None = None
        self.received_system_prompt: str | None = None
        HistoryTrackingProvider.last_instance = self

    async def generate(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 0,
        system_prompt: str | None = None,
        messages: List[dict] | None = None,
        **_: object,
    ) -> ProviderResponse:
        self.received_messages = messages or []
        self.received_system_prompt = system_prompt
        remembered = ""
        if self.received_messages:
            remembered = " ".join(
                part.get("content", "") for part in self.received_messages if part.get("role") == "assistant"
            )
        text = remembered or "stub response"
        return ProviderResponse(text=text, model=model or "stub", provider="stub")

    async def stream(
        self,
        prompt: str,
        model: str | None = None,
        *,
        runtime=None,
        **kwargs: object,
    ) -> AsyncIterator[str]:
        yield ""


@pytest.fixture(autouse=True)
def override_provider() -> None:
    """Temporarily replace the OpenAI provider with the history-tracking stub."""

    from core.providers.registries import _text_providers

    original = _text_providers.get("openai")
    register_text_provider("openai", HistoryTrackingProvider)
    try:
        yield
    finally:
        if original:
            _text_providers["openai"] = original
        else:
            _text_providers.pop("openai", None)
        HistoryTrackingProvider.last_instance = None


@pytest.mark.asyncio
async def test_conversation_history_reaches_provider() -> None:
    """The chat service should forward prior history to the provider."""

    service = ChatService(tts_service=MagicMock())
    settings = {"text": {"model": "gpt-4o-mini"}}

    history = [
        {"role": "user", "content": "My favourite colour is blue."},
        {"role": "assistant", "content": "I'll remember that your favourite colour is blue."},
    ]

    response = await service.generate_response(
        prompt="What colour do I like?",
        settings=settings,
        customer_id=101,
        user_input={"chat_history": history, "prompt": "What colour do I like?"},
    )

    provider_instance = HistoryTrackingProvider.last_instance
    assert provider_instance is not None
    assert provider_instance.received_messages is not None
    assert len(provider_instance.received_messages) == 3
    assert provider_instance.received_messages[0]["content"].startswith("My favourite colour")
    assert provider_instance.received_messages[-1]["content"] == "What colour do I like?"
    assert "favourite colour is blue" in (response.text or "")
