"""OpenAI text generation provider implementation.

This module provides the main OpenAI text provider class, which orchestrates
text generation by delegating to specialized modules for generation
(:mod:`generation`) and streaming (:mod:`streaming`).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, AsyncIterator, Dict, List, Optional

if TYPE_CHECKING:
    from features.chat.utils.websocket_runtime import WorkflowRuntime

from core.clients.ai import ai_clients
from core.exceptions import ProviderError, ValidationError
from core.providers.base import BaseTextProvider
from core.providers.capabilities import ProviderCapabilities
from core.pydantic_schemas import ProviderResponse
from core.streaming.manager import StreamingManager
from config.batch.defaults import (
    BATCH_MAX_FILE_SIZE_MB_OPENAI,
    BATCH_MAX_REQUESTS_OPENAI,
)

from core.providers.batch import OpenAIBatchOperations

from .generation import generate_text
from .openai_batch import prepare_openai_batch_requests, process_openai_batch_response
from .streaming import stream_text

logger = logging.getLogger(__name__)


class OpenAITextProvider(BaseTextProvider):
    """OpenAI text generation provider."""

    provider_name = "openai"

    def __init__(self) -> None:
        self.client = ai_clients.get("openai_async")
        if not self.client:
            raise ProviderError("OpenAI client not initialized", provider="openai")

        self.capabilities = ProviderCapabilities(
            streaming=True,
            reasoning=False,
            citations=False,
            audio_input=False,
            image_input=True,
            batch_api=True,
            batch_max_requests=BATCH_MAX_REQUESTS_OPENAI,
            batch_max_file_size_mb=BATCH_MAX_FILE_SIZE_MB_OPENAI,
        )

    @staticmethod
    def _is_reasoning_model(model: str) -> bool:
        """Return True if the supplied model is a reasoning model."""

        return model.startswith("o1-") or model.startswith("o1.")

    def _uses_responses_api(self) -> bool:
        """Return True when the configured model uses the Responses API."""

        if not self._model_config:
            return False
        return self._model_config.api_type == "responses_api"

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        system_prompt: Optional[str] = None,
        messages: Optional[list[dict[str, Any]]] = None,
        enable_reasoning: bool = False,
        reasoning_value: Optional[str] = None,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Generate a complete response (non-streaming)."""
        model_config = self._model_config
        if model is None:
            model = model_config.model_name if model_config else "gpt-4o-mini"
        is_reasoning_model = (
            model_config.is_reasoning_model
            if model_config
            else self._is_reasoning_model(model)
        )

        response = await generate_text(
            client=self.client,
            model_config=model_config,
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
            messages=messages,
            enable_reasoning=enable_reasoning,
            reasoning_value=reasoning_value,
            is_reasoning_model=is_reasoning_model,
            uses_responses_api=self._uses_responses_api(),
            **kwargs,
        )

        if response.reasoning:
            self.capabilities.reasoning = True

        return response

    async def generate_batch(
        self,
        requests: List[Dict[str, Any]],
        **kwargs: Any,
    ) -> List[ProviderResponse]:
        """Generate responses via OpenAI Batch API."""

        status_callback = kwargs.pop("status_callback", None)
        polling_interval = kwargs.pop("polling_interval", None)
        timeout_seconds = kwargs.pop("timeout", None)

        if not getattr(self.capabilities, "batch_api", False):
            return await super().generate_batch(requests, **kwargs)

        if not requests:
            return []

        batch_requests, request_map = prepare_openai_batch_requests(self, requests)
        batch_ops = OpenAIBatchOperations(self.client)

        try:
            results = await batch_ops.submit_and_wait(
                batch_requests,
                description=kwargs.get("description"),
                status_callback=status_callback,
                polling_interval=polling_interval,
                timeout=timeout_seconds,
            )
        except ProviderError:
            raise
        except Exception as exc:  # pragma: no cover - network failure
            logger.exception("OpenAI batch submission failed")
            raise ProviderError("OpenAI batch submission failed", provider="openai", original_error=exc) from exc

        return await process_openai_batch_response(self, requests, results)

    async def stream(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        system_prompt: Optional[str] = None,
        messages: Optional[list[dict[str, Any]]] = None,
        enable_reasoning: bool = False,
        reasoning_value: Optional[str] = None,
        runtime: Optional["WorkflowRuntime"] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str | dict[str, str]]:
        """Stream response chunks from OpenAI."""
        manager: StreamingManager | None = kwargs.pop("manager", None)
        model_config = self._model_config
        if model is None:
            model = model_config.model_name if model_config else "gpt-4o-mini"
        is_reasoning_model = (
            model_config.is_reasoning_model
            if model_config
            else self._is_reasoning_model(model)
        )

        # Pop settings from kwargs to avoid passing to stream_text
        kwargs.pop("settings", None)

        async for chunk in stream_text(
            client=self.client,
            model_config=model_config,
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
            messages=messages,
            enable_reasoning=enable_reasoning,
            reasoning_value=reasoning_value,
            is_reasoning_model=is_reasoning_model,
            uses_responses_api=self._uses_responses_api(),
            manager=manager,
            runtime=runtime,  
            **kwargs,
        ):
            yield chunk

    async def generate_with_reasoning(
        self,
        prompt: str,
        reasoning_effort: str = "medium",
        model: str = "gpt-5",
        **kwargs: Any,
    ) -> ProviderResponse:
        """Generate a response including reasoning traces for models."""

        if not self._is_reasoning_model(model):
            raise NotImplementedError(f"Model {model} doesn't support reasoning")

        self.capabilities.reasoning = True
        return await self.generate(
            prompt=prompt,
            model=model,
            enable_reasoning=True,
            reasoning_value=reasoning_effort,
            **kwargs,
        )
