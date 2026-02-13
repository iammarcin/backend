"""Groq text generation provider using the OpenAI-compatible API."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, AsyncIterator, Optional

if TYPE_CHECKING:
    from features.chat.utils.websocket_runtime import WorkflowRuntime

from core.clients.ai import ai_clients
from core.exceptions import ProviderError
from core.providers.capabilities import ProviderCapabilities
from core.pydantic_schemas import ProviderResponse
from core.providers.base import BaseTextProvider

logger = logging.getLogger(__name__)


def _extract_message_content(message: Any) -> str:
    """Return the text content from an OpenAI-style message object."""

    if hasattr(message, "content"):
        return getattr(message, "content", "") or ""
    if isinstance(message, dict):
        return str(message.get("content", ""))
    return ""


class GroqTextProvider(BaseTextProvider):
    """Text provider for Groq's OpenAI-compatible API."""

    def __init__(self) -> None:
        self.client = ai_clients.get("groq_async")
        if not self.client:
            raise ProviderError("Groq client not initialized", provider="groq")

        self.capabilities = ProviderCapabilities(
            streaming=True,
            reasoning=False,
            citations=False,
            audio_input=False,
            image_input=False,
        )

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = "llama3-70b-8192",
        temperature: float = 0.1,
        max_tokens: int = 4096,
        system_prompt: Optional[str] = None,
        messages: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Generate a non-streaming response."""

        if not prompt:
            raise ProviderError("Prompt cannot be empty", provider="groq")

        final_messages = messages
        if final_messages is None:
            final_messages = []
            if system_prompt:
                final_messages.append({"role": "system", "content": system_prompt})
            final_messages.append({"role": "user", "content": prompt})

        filtered_kwargs = dict(kwargs)
        filtered_kwargs.pop("manager", None)
        filtered_kwargs.pop("system_prompt", None)
        filtered_kwargs.pop("enable_reasoning", None)
        filtered_kwargs.pop("reasoning_value", None)
        filtered_kwargs.pop("reasoning_effort", None)
        filtered_kwargs.pop("settings", None)

        params = {
            "model": model or "llama3-70b-8192",
            "messages": final_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **filtered_kwargs,
        }

        logger.info("Calling Groq generate with model: %s", params["model"])

        try:
            response = await self.client.chat.completions.create(**params)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Groq generate error: %s", exc)
            raise ProviderError(f"Groq error: {exc}", provider="groq") from exc

        choice = response.choices[0]
        message = getattr(choice, "message", None)
        text = _extract_message_content(message)

        metadata = {
            "finish_reason": getattr(choice, "finish_reason", None),
            "usage": response.usage.model_dump() if getattr(response, "usage", None) else None,
        }

        return ProviderResponse(
            text=text,
            model=params["model"],
            provider="groq",
            metadata=metadata,
        )

    async def stream(
        self,
        prompt: str,
        model: Optional[str] = "llama3-70b-8192",
        temperature: float = 0.1,
        max_tokens: int = 4096,
        system_prompt: Optional[str] = None,
        messages: Optional[list[dict[str, Any]]] = None,
        runtime: Optional["WorkflowRuntime"] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream text chunks from Groq."""

        final_messages = messages
        if final_messages is None:
            final_messages = []
            if system_prompt:
                final_messages.append({"role": "system", "content": system_prompt})
            final_messages.append({"role": "user", "content": prompt})

        # Pop the streaming manager if provided to avoid leaking it to the SDK.
        kwargs.pop("manager", None)

        filtered_kwargs = dict(kwargs)
        filtered_kwargs.pop("system_prompt", None)
        filtered_kwargs.pop("enable_reasoning", None)
        filtered_kwargs.pop("reasoning_value", None)
        filtered_kwargs.pop("reasoning_effort", None)
        filtered_kwargs.pop("settings", None)

        params = {
            "model": model or "llama3-70b-8192",
            "messages": final_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            **filtered_kwargs,
        }

        try:
            stream = await self.client.chat.completions.create(**params)
        except Exception as exc:  # pragma: no cover
            logger.error("Groq stream error: %s", exc)
            raise ProviderError(f"Groq streaming error: {exc}", provider="groq") from exc

        try:
            async for chunk in stream:
                # Check cancellation
                if runtime and runtime.is_cancelled():
                    logger.info(
                        "Groq stream cancelled by user (model=%s)",
                        params["model"],
                    )
                    break  # Exit loop, close stream

                choice = chunk.choices[0]
                delta = getattr(choice, "delta", None)
                content = None
                if hasattr(delta, "content"):
                    content = getattr(delta, "content", None)
                elif isinstance(delta, dict):
                    content = delta.get("content")
                if content:
                    yield content
        except asyncio.CancelledError:
            # Handle explicit task cancellation
            logger.info("Groq stream task cancelled (model=%s)", params["model"])
            raise  # Re-raise for cleanup
