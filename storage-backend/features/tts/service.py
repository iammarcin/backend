"""High-level orchestration for text-to-speech operations."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator, Callable, Dict

from core.providers.factory import get_tts_provider
from core.streaming.manager import StreamingManager
from infrastructure.aws.storage import StorageService

from features.tts.schemas.requests import TTSGenerateRequest, TTSUserSettings

from .service_generate import generate_audio
from .service_models import TTSBillingResult, TTSGenerationResult, TTSStreamingMetadata
from .service_stream_http import prepare_http_stream
from .service_stream_queue import stream_text_queue_audio
from .service_stream_text import stream_text_audio

logger = logging.getLogger(__name__)


class TTSService:
    """Coordinate provider selection, preprocessing, and storage for TTS."""

    def __init__(
        self,
        *,
        provider_resolver: Callable[[Dict[str, Any]], Any] = get_tts_provider,
        storage_service_factory: Callable[[], StorageService] | None = None,
    ) -> None:
        self._provider_resolver = provider_resolver
        self._storage_service_factory = storage_service_factory or StorageService

    async def generate(self, request: TTSGenerateRequest) -> TTSGenerationResult:
        return await generate_audio(
            request=request,
            provider_resolver=self._provider_resolver,
            storage_service_factory=self._storage_service_factory,
        )

    async def get_billing(self, settings: TTSUserSettings) -> TTSBillingResult:
        provider = self._provider_resolver(settings.to_provider_payload())
        logger.info("Fetching TTS billing information via provider %s", provider.__class__.__name__)
        result = await provider.get_billing()
        return TTSBillingResult(status="completed", result=dict(result))

    async def stream_text(
        self,
        *,
        text: str,
        customer_id: int,
        user_settings: TTSUserSettings,
        manager: StreamingManager,
        timings: Dict[str, float] | None = None,
        runtime=None,
    ) -> TTSStreamingMetadata:
        return await stream_text_audio(
            text=text,
            customer_id=customer_id,
            user_settings=user_settings,
            manager=manager,
            provider_resolver=self._provider_resolver,
            storage_service_factory=self._storage_service_factory,
            timings=timings,
            runtime=runtime,
        )

    async def stream_from_text_queue(
        self,
        *,
        text_queue: asyncio.Queue[str | None],
        customer_id: int,
        user_settings: TTSUserSettings,
        manager: StreamingManager,
        timings: Dict[str, float] | None = None,
    ) -> TTSStreamingMetadata:
        """Stream audio from a queue of text chunks during text generation."""

        return await stream_text_queue_audio(
            text_queue=text_queue,
            customer_id=customer_id,
            user_settings=user_settings,
            manager=manager,
            provider_resolver=self._provider_resolver,
            storage_service_factory=self._storage_service_factory,
            timings=timings,
        )

    async def stream_http(
        self, request: TTSGenerateRequest
    ) -> tuple[str, AsyncIterator[bytes], Dict[str, Any]]:
        media_type, iterator, metadata = await prepare_http_stream(
            request=request,
            provider_resolver=self._provider_resolver,
        )
        return media_type, iterator, metadata


__all__ = ["TTSService", "TTSGenerationResult", "TTSBillingResult", "TTSStreamingMetadata"]
