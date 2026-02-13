"""Streaming helpers for WebSocket-based TTS delivery."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List

from core.exceptions import ValidationError
from core.streaming.manager import StreamingManager

from infrastructure.aws.storage import StorageService

from features.tts.schemas.requests import TTSUserSettings

from .request_builder import build_tts_requests
from .service_models import TTSStreamingMetadata
from .service_persistence import persist_audio_and_metadata
from .service_streaming import stream_requests
from .test_mode import emit_test_stream


logger = logging.getLogger(__name__)


async def stream_text_audio(
    *,
    text: str,
    customer_id: int,
    user_settings: TTSUserSettings,
    manager: StreamingManager,
    provider_resolver: Callable[[Dict[str, Any]], Any],
    storage_service_factory: Callable[[], StorageService],
    timings: Dict[str, float] | None = None,
    runtime=None,
) -> TTSStreamingMetadata:
    """Stream audio chunks through the supplied streaming manager."""

    if not text.strip():
        raise ValidationError("Text input is required for streaming", field="text")

    if user_settings.general.return_test_data:
        return await emit_test_stream(manager, user_settings, customer_id=customer_id)

    batch = build_tts_requests(
        text=text,
        user_settings=user_settings,
        customer_id=customer_id,
        provider_resolver=provider_resolver,
    )

    websocket_format = batch.provider.get_websocket_format()
    logger.debug(
        "Using websocket audio format '%s' for provider '%s'",
        websocket_format,
        getattr(batch.provider, "name", type(batch.provider).__name__),
    )
    for request in batch.requests:
        request.format = websocket_format
    batch.format = websocket_format

    if timings is None:
        timings = {}

    chunk_length_schedule: List[int] | None = None
    if getattr(user_settings.tts, "chunk_schedule", None):
        chunk_length_schedule = user_settings.tts.chunk_schedule
        logger.debug("Using chunk_length_schedule from settings: %s", chunk_length_schedule)

    metadata, audio_bytes = await stream_requests(
        manager=manager,
        provider=batch.provider,
        requests=batch.requests,
        metadata_provider=getattr(batch.provider, "name", "tts"),
        resolved_model=batch.model,
        resolved_voice=batch.voice,
        resolved_format=batch.format or "mp3",
        timings=timings,
        chunk_length_schedule=chunk_length_schedule,
        runtime=runtime,
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


__all__ = ["stream_text_audio"]
