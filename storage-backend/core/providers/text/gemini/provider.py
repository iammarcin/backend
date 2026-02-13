"""Google Gemini text generation provider."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, AsyncIterator, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from features.chat.utils.websocket_runtime import WorkflowRuntime

from google.genai import types  # type: ignore

from core.clients.ai import ai_clients
from core.exceptions import ProviderError, ValidationError
from core.providers.base import BaseTextProvider
from core.providers.batch import GeminiBatchOperations
from core.providers.capabilities import ProviderCapabilities
from core.pydantic_schemas import ProviderResponse

from config.batch.defaults import (
    BATCH_MAX_FILE_SIZE_MB_GEMINI,
    BATCH_MAX_REQUESTS_GEMINI,
)

from .batch import process_gemini_batch_response, transform_to_gemini_format
from .operations import generate_text, stream_text

logger = logging.getLogger(__name__)


class GeminiTextProvider(BaseTextProvider):
    """Text provider backed by Google Gemini."""

    provider_name = "gemini"

    def __init__(self) -> None:
        self.client = ai_clients.get("gemini")
        if not self.client:
            raise ProviderError("Gemini client not initialized", provider="gemini")

        self.capabilities = ProviderCapabilities(
            streaming=True,
            reasoning=True,
            citations=False,
            audio_input=True,
            image_input=True,
            batch_api=True,
            batch_max_requests=BATCH_MAX_REQUESTS_GEMINI,
            batch_max_file_size_mb=BATCH_MAX_FILE_SIZE_MB_GEMINI,
        )

    def _get_async_client(self) -> Any:
        """Return the async client if available, otherwise None."""

        return getattr(self.client, "aio", None)

    async def _generate_async(
        self,
        model: str,
        contents: list[Any],
        config: types.GenerateContentConfig,
    ) -> Any:
        async_client = self._get_async_client()
        if async_client and hasattr(async_client, "models"):
            return await async_client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )

        return await asyncio.to_thread(
            self.client.models.generate_content,  # type: ignore[attr-defined]
            model=model,
            contents=contents,
            config=config,
        )

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        system_prompt: Optional[str] = None,
        messages: Optional[list[dict[str, Any]]] = None,
        enable_reasoning: bool = False,
        reasoning_value: Optional[int] = None,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Generate a non-streaming response."""

        # Pop settings to avoid passing to generate_text
        kwargs.pop("settings", None)
        return await generate_text(
            self,
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
            messages=messages,
            enable_reasoning=enable_reasoning,
            reasoning_value=reasoning_value,
            request_kwargs=kwargs,
        )

    async def stream(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        system_prompt: Optional[str] = None,
        messages: Optional[list[dict[str, Any]]] = None,
        enable_reasoning: bool = False,
        reasoning_value: Optional[int] = None,
        runtime: Optional["WorkflowRuntime"] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str | dict[str, Any]]:
        """Stream text chunks from Gemini."""

        # Pop settings to avoid passing to stream_text
        kwargs.pop("settings", None)
        async for chunk in stream_text(
            self,
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
            messages=messages,
            enable_reasoning=enable_reasoning,
            reasoning_value=reasoning_value,
            runtime=runtime,
            request_kwargs=kwargs,
        ):
            yield chunk

    async def generate_batch(
        self,
        requests: List[Dict[str, Any]],
        **kwargs: Any,
    ) -> List[ProviderResponse]:
        """Generate multiple completions using the Gemini Batch API."""

        if not getattr(self.capabilities, "batch_api", False):
            return await super().generate_batch(requests, **kwargs)

        if not requests:
            return []

        default_model = self._model_config.model_name if self._model_config else "gemini-2.5-flash"
        gemini_requests, request_map = transform_to_gemini_format(requests, default_model)

        use_file = len(gemini_requests) > 100
        batch_ops = GeminiBatchOperations(self.client)

        try:
            results = await batch_ops.submit_and_wait(
                model=default_model,
                requests=gemini_requests,
                use_file=use_file,
            )
        except ProviderError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Gemini batch submission failed")
            raise ProviderError("Gemini batch submission failed", provider="google", original_error=exc) from exc

        return await process_gemini_batch_response(self, requests, results)

    async def generate_with_audio(
        self,
        audio_data: bytes,
        prompt: Optional[str] = None,
        model: Optional[str] = None,
        mime_type: str = "audio/wav",
        **kwargs: Any,
    ) -> ProviderResponse:
        """Generate a response using audio input."""

        if not audio_data:
            raise ProviderError("Audio input required", provider="gemini")

        audio_part = types.Part.from_bytes(data=audio_data, mime_type=mime_type)

        return await self.generate(
            prompt="" if prompt is None else prompt,
            model=model,
            audio_parts=[audio_part],
            **kwargs,
        )


__all__ = ["GeminiTextProvider"]
