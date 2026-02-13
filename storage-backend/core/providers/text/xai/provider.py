"""xAI Grok text generation provider backed by the official SDK."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncIterator, Optional

if TYPE_CHECKING:
    from features.chat.utils.websocket_runtime import WorkflowRuntime

from google.genai import types  # type: ignore[attr-defined]

from core.clients.ai import ai_clients
from core.exceptions import ProviderError
from core.providers.base import BaseTextProvider
from core.providers.capabilities import ProviderCapabilities
from core.pydantic_schemas import ProviderResponse

from .operations import generate_text, stream_text


class XaiTextProvider(BaseTextProvider):
    """Text provider for xAI's Grok models using the official SDK."""

    provider_name = "xai"

    def __init__(self) -> None:
        self.client = ai_clients.get("xai_async")
        if not self.client:
            raise ProviderError("xAI client not initialized", provider="xai")

        self.capabilities = ProviderCapabilities(
            streaming=True,
            reasoning=False,
            citations=True,
            audio_input=False,
            image_input=True,
            file_input=True,
            function_calling=True,
        )

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        system_prompt: Optional[str] = None,
        messages: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Generate a complete response from xAI."""

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
            request_kwargs=kwargs,
        )

    async def stream(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        system_prompt: Optional[str] = None,
        messages: Optional[list[dict[str, Any]]] = None,
        runtime: Optional["WorkflowRuntime"] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str | dict[str, Any]]:
        """Stream response chunks from xAI."""

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
            runtime=runtime,
            request_kwargs=kwargs,
        ):
            yield chunk

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
            raise ProviderError("Audio input required", provider="xai")

        audio_part = types.Part.from_bytes(data=audio_data, mime_type=mime_type)

        return await self.generate(
            prompt="" if prompt is None else prompt,
            model=model,
            audio_parts=[audio_part],
            **kwargs,
        )


__all__ = ["XaiTextProvider"]
