"""Perplexity Sonar provider implementation."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, AsyncIterator, Dict, Iterable, Optional

if TYPE_CHECKING:
    from features.chat.utils.websocket_runtime import WorkflowRuntime

from core.clients.ai import ai_clients
from core.exceptions import ProviderError
from core.providers.capabilities import ProviderCapabilities
from core.pydantic_schemas import ProviderResponse
from core.providers.base import BaseTextProvider

logger = logging.getLogger(__name__)


class PerplexityTextProvider(BaseTextProvider):
    """Text provider that surfaces Perplexity citations."""

    def __init__(self) -> None:
        self.client = ai_clients.get("perplexity_async")
        if not self.client:
            raise ProviderError("Perplexity client not initialized", provider="perplexity")

        self.capabilities = ProviderCapabilities(
            streaming=True,
            reasoning=True,
            citations=True,
            audio_input=False,
            image_input=False,
        )

    @staticmethod
    def _normalise_citations(raw_citations: Iterable[Any]) -> list[Dict[str, Any]]:
        """Ensure citations conform to ProviderResponse expectations."""

        normalised: list[Dict[str, Any]] = []
        for entry in raw_citations:
            if entry is None:
                continue

            if isinstance(entry, dict):
                normalised.append(entry)
                continue

            dump_callable = None
            if hasattr(entry, "model_dump") and callable(getattr(entry, "model_dump")):
                dump_callable = getattr(entry, "model_dump")
            elif hasattr(entry, "to_dict") and callable(getattr(entry, "to_dict")):
                dump_callable = getattr(entry, "to_dict")
            elif hasattr(entry, "dict") and callable(getattr(entry, "dict")):
                dump_callable = getattr(entry, "dict")

            if dump_callable:
                try:
                    candidate = dump_callable()
                    if isinstance(candidate, dict):
                        normalised.append(candidate)
                        continue
                except Exception:  # pragma: no cover - defensive fallback
                    pass

            url = None
            if isinstance(entry, str):
                url = entry.strip() or None
            elif hasattr(entry, "url"):
                url = getattr(entry, "url", None)

            if url:
                normalised.append({"url": url})

        return normalised

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = "sonar",
        temperature: float = 0.2,
        max_tokens: int = 2048,
        messages: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Generate a response and return citations when available."""

        if not prompt:
            raise ProviderError("Prompt cannot be empty", provider="perplexity")

        final_messages = messages
        if final_messages is None:
            final_messages = [{"role": "user", "content": prompt}]

        filtered_kwargs = dict(kwargs)
        filtered_kwargs.pop("manager", None)
        filtered_kwargs.pop("system_prompt", None)
        filtered_kwargs.pop("settings", None)

        logger.debug(
            "Perplexity API call: model=%s, messages_count=%d, temperature=%.2f, max_tokens=%d, reasoning_effort=%s",
            model or "sonar",
            len(final_messages),
            temperature,
            max_tokens,
            filtered_kwargs.get("reasoning_effort"),
        )

        try:
            response = await self.client.chat.completions.create(
                model=model or "sonar",
                messages=final_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **filtered_kwargs,
            )
        except Exception as exc:  # pragma: no cover
            logger.error("Perplexity generate error: %s", exc)
            raise ProviderError(f"Perplexity error: {exc}", provider="perplexity") from exc

        choice = response.choices[0]
        message = getattr(choice, "message", None)
        text = ""
        if message:
            text = getattr(message, "content", None) or ""

        citations = []
        if getattr(response, "citations", None):
            citations = list(response.citations)
        elif message and getattr(message, "citations", None):
            citations = list(message.citations)

        normalised_citations = None
        if citations:
            normalised_citations = self._normalise_citations(citations) or None

        metadata = {
            "finish_reason": getattr(choice, "finish_reason", None),
            "usage": response.usage.model_dump() if getattr(response, "usage", None) else None,
        }

        return ProviderResponse(
            text=text,
            model=model or "sonar",
            provider="perplexity",
            citations=normalised_citations,
            metadata=metadata,
        )

    async def stream(
        self,
        prompt: str,
        model: Optional[str] = "sonar",
        temperature: float = 0.2,
        max_tokens: int = 2048,
        messages: Optional[list[dict[str, Any]]] = None,
        runtime: Optional["WorkflowRuntime"] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream text chunks from Perplexity."""

        final_messages = messages
        if final_messages is None:
            final_messages = [{"role": "user", "content": prompt}]

        filtered_kwargs = dict(kwargs)
        filtered_kwargs.pop("manager", None)
        filtered_kwargs.pop("system_prompt", None)
        filtered_kwargs.pop("settings", None)

        logger.debug(
            "Perplexity stream: model=%s, messages_count=%d, temperature=%.2f, max_tokens=%d",
            model or "sonar",
            len(final_messages),
            temperature,
            max_tokens,
        )

        try:
            stream = await self.client.chat.completions.create(
                model=model or "sonar",
                messages=final_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                **filtered_kwargs,
            )
        except Exception as exc:  # pragma: no cover
            logger.error("Perplexity stream error: %s", exc)
            raise ProviderError(f"Perplexity streaming error: {exc}", provider="perplexity") from exc

        try:
            async for chunk in stream:
                # Check cancellation
                if runtime and runtime.is_cancelled():
                    logger.info(
                        "Perplexity stream cancelled by user (model=%s)",
                        model or "sonar",
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
            logger.info("Perplexity stream task cancelled (model=%s)", model or "sonar")
            raise  # Re-raise for cleanup
