"""Queue-based streaming helpers for TTS delivery during text generation."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, List

from core.streaming.manager import StreamingManager
from infrastructure.aws.storage import StorageService

from features.tts.schemas.requests import TTSUserSettings
from .service_models import TTSStreamingMetadata
from .service_persistence import persist_audio_and_metadata
from .service_stream_queue_helpers import (
    perform_fallback_buffered_stream,
    stream_audio_from_queue,
)
from .test_mode import emit_test_stream


logger = logging.getLogger(__name__)


async def stream_text_queue_audio(
    *,
    text_queue: asyncio.Queue[str | None],
    customer_id: int,
    user_settings: TTSUserSettings,
    manager: StreamingManager,
    provider_resolver: Callable[[Dict[str, Any]], Any],
    storage_service_factory: Callable[[], StorageService],
    timings: Dict[str, float] | None = None,
) -> TTSStreamingMetadata:
    """Stream audio while consuming text chunks from a queue."""

    if user_settings.general.return_test_data:
        return await emit_test_stream(manager, user_settings, customer_id=customer_id)

    provider_payload = user_settings.to_provider_payload()
    provider = provider_resolver(provider_payload)

    supports_streaming = bool(getattr(provider, "supports_input_stream", False))
    if not supports_streaming:
        logger.warning(
            "Provider %s does not support input streaming, falling back to buffered mode",
            getattr(provider, "name", type(provider).__name__),
        )
        return await perform_fallback_buffered_stream(
            text_queue=text_queue,
            customer_id=customer_id,
            user_settings=user_settings,
            manager=manager,
            provider=provider,
            storage_service_factory=storage_service_factory,
            timings=timings,
        )

    provider_name = getattr(provider, "name", "tts")
    audio_format = provider.get_websocket_format()
    logger.debug(
        "Using websocket audio format '%s' for provider '%s'",
        audio_format,
        provider_name,
    )

    if timings is None:
        timings = {}

    chunk_length_schedule: List[int] | None = getattr(user_settings.tts, "chunk_schedule", None)
    if chunk_length_schedule:
        logger.debug("Using chunk_length_schedule from settings: %s", chunk_length_schedule)

    await manager.send_to_queues(
        {
            "type": "tts_started",
            "content": {
                "provider": provider_name,
                "model": user_settings.tts.model,
                "voice": user_settings.tts.voice,
                "format": audio_format,
                "text_chunk_count": manager.get_tts_chunks_sent() if manager.is_tts_enabled() else None,
            },
        }
    )

    metadata, audio_bytes = await stream_audio_from_queue(
        provider=provider,
        provider_name=provider_name,
        text_queue=text_queue,
        manager=manager,
        user_settings=user_settings,
        audio_format=audio_format,
        chunk_length_schedule=chunk_length_schedule,
        timings=timings,
    )

    if audio_bytes:
        try:
            result_url, storage_metadata = await persist_audio_and_metadata(
                storage_service_factory=storage_service_factory,
                audio_bytes=audio_bytes,
                user_settings=user_settings,
                customer_id=customer_id,
                provider_name=metadata.provider,
                resolved_model=metadata.model,
                resolved_voice=metadata.voice,
                resolved_format=metadata.format,
                chunk_count=metadata.audio_chunk_count,
                extra_metadata={"text_chunk_count": metadata.text_chunk_count},
            )
            metadata.audio_file_url = result_url
            metadata.storage_metadata = storage_metadata
            metadata.format = storage_metadata.get("format", metadata.format)

            # Send simple tts_file_uploaded - consistent with standard flow
            await manager.send_to_queues({
                "type": "tts_file_uploaded",
                "content": {"audio_url": result_url}
            })
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Failed to persist streamed TTS audio: %s", exc, exc_info=True)

    return metadata


__all__ = ["stream_text_queue_audio"]
