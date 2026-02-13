"""Thin wrapper exposing the streaming workflows as a cohesive service."""

from __future__ import annotations

from typing import Any, AsyncIterator, Dict, Optional, Callable

from core.pydantic_schemas import ProviderResponse
from core.streaming.manager import StreamingManager
from features.tts.service import TTSService

from features.chat.utils.prompt_utils import PromptInput

from .core import generate_response as generate_response_impl
from .core import stream_response as stream_response_impl
from .core import stream_response_chunks as stream_response_chunks_impl
from .helpers import get_helper


class ChatService:
    """Business logic for chat streaming operations."""

    def __init__(self, *, tts_service: TTSService | None = None) -> None:
        if tts_service is not None:
            self._tts_service = tts_service
        else:
            tts_factory: Callable[[], TTSService] = get_helper("TTSService", TTSService)
            self._tts_service = tts_factory()

    async def stream_response(
        self,
        *,
        prompt: PromptInput,
        settings: Dict[str, Any],
        customer_id: int,
        manager: StreamingManager,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        timings: Optional[Dict[str, float]] = None,
        user_input: Optional[Dict[str, Any]] = None,
        runtime=None,  # ✅ NEW
    ) -> Dict[str, Any]:
        """Delegate to the core streaming workflow with the configured TTS service."""

        return await stream_response_impl(
            prompt=prompt,
            settings=settings,
            customer_id=customer_id,
            manager=manager,
            model=model,
            system_prompt=system_prompt,
            timings=timings,
            tts_service=self._tts_service,
            user_input=user_input,
            runtime=runtime,  # ✅ NEW
        )

    async def generate_response(
        self,
        *,
        prompt: PromptInput,
        settings: Dict[str, Any],
        customer_id: int,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        user_input: Optional[Dict[str, Any]] = None,
    ) -> ProviderResponse:
        """Generate a full response without streaming."""

        provider_response = await generate_response_impl(
            prompt=prompt,
            settings=settings,
            customer_id=customer_id,
            model=model,
            system_prompt=system_prompt,
            user_input=user_input,
        )
        metadata = provider_response.metadata
        tool_calls: list[Dict[str, Any]] | None = None
        if isinstance(metadata, dict):
            tool_calls_candidate = metadata.get("tool_calls")
            if isinstance(tool_calls_candidate, list):
                tool_calls = [call for call in tool_calls_candidate if isinstance(call, dict)]

        if tool_calls:
            provider_response.tool_calls = tool_calls
            provider_response.requires_tool_action = True

        return provider_response

    async def stream_response_chunks(
        self,
        *,
        prompt: PromptInput,
        settings: Dict[str, Any],
        customer_id: int,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        user_input: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[str]:
        """Yield provider chunks for Server-Sent Events pipelines."""

        async for chunk in stream_response_chunks_impl(
            prompt=prompt,
            settings=settings,
            customer_id=customer_id,
            model=model,
            system_prompt=system_prompt,
            user_input=user_input,
        ):
            yield chunk


__all__ = ["ChatService", "get_helper"]
