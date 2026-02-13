"""DeepSeek text generation provider."""

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


class DeepSeekTextProvider(BaseTextProvider):
    """Text provider implementation for DeepSeek models."""

    def __init__(self) -> None:
        self.client = ai_clients.get("deepseek_async")
        if not self.client:
            raise ProviderError("DeepSeek client not initialized", provider="deepseek")

        self.capabilities = ProviderCapabilities(
            streaming=True,
            reasoning=True,
            citations=False,
            audio_input=False,
            image_input=False,
        )

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = "deepseek-chat",
        temperature: float = 0.1,
        max_tokens: int = 4096,
        system_prompt: Optional[str] = None,
        messages: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Generate a non-streaming response."""

        if not prompt:
            raise ProviderError("Prompt cannot be empty", provider="deepseek")

        final_messages = messages
        if final_messages is None:
            final_messages = []
            if system_prompt:
                final_messages.append({"role": "system", "content": system_prompt})
            final_messages.append({"role": "user", "content": prompt})

        kwargs.pop("manager", None)

        filtered_kwargs = dict(kwargs)
        filtered_kwargs.pop("system_prompt", None)
        filtered_kwargs.pop("enable_reasoning", None)
        filtered_kwargs.pop("reasoning_value", None)
        filtered_kwargs.pop("reasoning_effort", None)
        filtered_kwargs.pop("settings", None)

        params = {
            "model": model or "deepseek-chat",
            "messages": final_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **filtered_kwargs,
        }

        logger.debug(
            "DeepSeek API call: model=%s, messages_count=%d, temperature=%.2f, max_tokens=%d",
            params["model"],
            len(final_messages),
            params.get("temperature", 0.0),
            params.get("max_tokens", 0),
        )

        try:
            response = await self.client.chat.completions.create(**params)
        except Exception as exc:  # pragma: no cover
            logger.error("DeepSeek generate error: %s", exc)
            raise ProviderError(f"DeepSeek error: {exc}", provider="deepseek") from exc

        choice = response.choices[0]
        message = getattr(choice, "message", None)
        text = ""
        if message:
            text = getattr(message, "content", "") or message.get("content", "")

        metadata = {
            "finish_reason": getattr(choice, "finish_reason", None),
            "usage": response.usage.model_dump() if getattr(response, "usage", None) else None,
        }

        return ProviderResponse(
            text=text,
            model=params["model"],
            provider="deepseek",
            metadata=metadata,
        )

    async def stream(
        self,
        prompt: str,
        model: Optional[str] = "deepseek-chat",
        temperature: float = 0.1,
        max_tokens: int = 4096,
        system_prompt: Optional[str] = None,
        messages: Optional[list[dict[str, Any]]] = None,
        runtime: Optional["WorkflowRuntime"] = None, 
        **kwargs: Any,
    ) -> AsyncIterator[str | dict[str, str]]:
        """Stream chunks from DeepSeek."""

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
            "model": model or "deepseek-chat",
            "messages": final_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            **filtered_kwargs,
        }

        logger.debug(
            "DeepSeek stream: model=%s, messages_count=%d, temperature=%.2f, max_tokens=%d",
            params["model"],
            len(final_messages),
            params.get("temperature", 0.0),
            params.get("max_tokens", 0),
        )

        try:
            stream = await self.client.chat.completions.create(**params)
        except Exception as exc:  # pragma: no cover
            logger.error("DeepSeek stream error: %s", exc)
            raise ProviderError(f"DeepSeek streaming error: {exc}", provider="deepseek") from exc

        try:
            async for chunk in stream:
                # Check cancellation
                if runtime and runtime.is_cancelled():
                    logger.info(
                        "DeepSeek stream cancelled by user (model=%s)",
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

                reasoning = None
                if hasattr(delta, "reasoning_content"):
                    reasoning = getattr(delta, "reasoning_content", None)
                elif isinstance(delta, dict):
                    reasoning = delta.get("reasoning_content")
                if reasoning:
                    yield {"type": "reasoning", "content": reasoning}
        except asyncio.CancelledError:
            # Handle explicit task cancellation
            logger.info("DeepSeek stream task cancelled (model=%s)", params["model"])
            raise  # Re-raise for cleanup

    async def generate_with_reasoning(
        self,
        prompt: str,
        reasoning_effort: str = "medium",
        model: Optional[str] = "deepseek-reasoner",
        **kwargs: Any,
    ) -> ProviderResponse:
        """Generate with a reasoning-enabled DeepSeek model."""

        kwargs.setdefault("temperature", 0.0)
        return await self.generate(prompt=prompt, model=model, **kwargs)
