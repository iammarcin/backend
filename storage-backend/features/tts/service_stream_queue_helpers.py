"""Helper functions for queue-based TTS streaming."""

from __future__ import annotations

import asyncio
import base64
import logging
import time
from io import BytesIO
from typing import Any, Callable, Dict, List

from core.exceptions import ValidationError
from core.streaming.manager import StreamingManager
from infrastructure.aws.storage import StorageService

from features.tts.schemas.requests import TTSUserSettings

from .service_models import TTSStreamingMetadata
from .service_stream_text import stream_text_audio


logger = logging.getLogger(__name__)


async def stream_audio_from_queue(
    *,
    provider: Any,
    provider_name: str,
    text_queue: asyncio.Queue[str | None],
    manager: StreamingManager,
    user_settings: TTSUserSettings,
    audio_format: str,
    chunk_length_schedule: List[int] | None,
    timings: Dict[str, float],
) -> tuple[TTSStreamingMetadata, bytes]:
    """Consume the text queue via provider streaming API."""

    if not hasattr(provider, "stream_from_text_queue"):
        raise ValidationError(
            f"Provider {provider_name} does not support queue-based streaming",
            field="tts",
        )

    text_chunk_count = manager.get_tts_chunks_sent() if manager.is_tts_enabled() else 0
    audio_buffer = BytesIO()
    audio_chunk_count = 0

    try:
        timings["tts_request_sent_time"] = time.time()

        async for audio_chunk_b64 in provider.stream_from_text_queue(
            text_queue=text_queue,
            voice=user_settings.tts.voice,
            model=user_settings.tts.model,
            audio_format=audio_format,
            voice_settings=user_settings.tts.as_provider_settings(),
            chunk_length_schedule=chunk_length_schedule,
        ):
            if not audio_chunk_b64:
                continue

            if audio_chunk_count == 0 and "tts_first_response_time" not in timings:
                timings["tts_first_response_time"] = time.time()
                first_chunk_latency = (
                    timings["tts_first_response_time"]
                    - timings.get("tts_request_sent_time", 0.0)
                )
                logger.info(
                    "First TTS audio chunk received (latency: %.2fms)",
                    first_chunk_latency * 1000,
                )

            manager.collect_chunk(audio_chunk_b64, "audio")
            await manager.send_to_queues({"type": "audio_chunk", "content": audio_chunk_b64})

            try:
                audio_bytes = base64.b64decode(audio_chunk_b64)
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning("Failed to decode audio chunk: %s", exc)
                continue

            audio_buffer.write(audio_bytes)
            audio_chunk_count += 1

        if audio_chunk_count == 0:
            await manager.send_to_queues(
                {
                    "type": "tts_error",
                    "content": {
                        "message": "No audio produced",
                        "provider": provider_name,
                    },
                }
            )
            # Send tts_completed so client doesn't hang waiting for completion signal
            await manager.send_to_queues({"type": "tts_completed", "content": ""})
            raise ValidationError("TTS provider returned no audio chunks", field="tts")

        text_chunk_count = (
            manager.get_tts_chunks_sent()
            if manager.is_tts_enabled()
            else text_chunk_count
        )

        await manager.send_to_queues(
            {
                "type": "tts_generation_completed",
                "content": {
                    "provider": provider_name,
                    "model": user_settings.tts.model,
                    "voice": user_settings.tts.voice,
                    "format": audio_format,
                    "audio_chunk_count": audio_chunk_count,
                    "text_chunk_count": text_chunk_count,
                },
            }
        )
        await manager.send_to_queues({"type": "tts_completed", "content": ""})

        timings["tts_response_time"] = time.time()
        logger.info(
            "TTS streaming completed (audio_chunks=%d, text_chunks=%d)",
            audio_chunk_count,
            text_chunk_count,
        )

    except Exception as exc:
        logger.error("TTS queue streaming failed: %s", exc, exc_info=True)
        await manager.send_to_queues(
            {
                "type": "tts_error",
                "content": {
                    "message": f"TTS streaming failed: {exc}",
                    "provider": provider_name,
                },
            }
        )
        # Send tts_completed so client doesn't hang waiting for completion signal
        await manager.send_to_queues({"type": "tts_completed", "content": ""})
        raise

    audio_buffer.seek(0)
    metadata = TTSStreamingMetadata(
        provider=provider_name,
        model=user_settings.tts.model,
        voice=user_settings.tts.voice,
        format=audio_format,
        text_chunk_count=text_chunk_count,
        audio_chunk_count=audio_chunk_count,
    )

    return metadata, audio_buffer.getvalue()


async def perform_fallback_buffered_stream(
    *,
    text_queue: asyncio.Queue[str | None],
    customer_id: int,
    user_settings: TTSUserSettings,
    manager: StreamingManager,
    provider: Any,
    storage_service_factory: Callable[[], StorageService],
    timings: Dict[str, float] | None,
) -> TTSStreamingMetadata:
    """Collect all queued text and reuse buffered streaming logic."""

    logger.info("Using buffered fallback mode for TTS streaming")

    text_chunks: list[str] = []
    while True:
        try:
            chunk = await asyncio.wait_for(text_queue.get(), timeout=30.0)
        except asyncio.TimeoutError:
            logger.warning("Timeout waiting for text chunks in fallback mode")
            break

        if chunk is None:
            break
        text_chunks.append(chunk)

    full_text = "".join(text_chunks)
    if not full_text.strip():
        raise ValidationError("No text received from queue for TTS", field="tts")

    logger.info(
        "Collected %d text chunks (%d chars) for buffered TTS",
        len(text_chunks),
        len(full_text),
    )

    return await stream_text_audio(
        text=full_text,
        customer_id=customer_id,
        user_settings=user_settings,
        manager=manager,
        provider_resolver=lambda _: provider,
        storage_service_factory=storage_service_factory,
        timings=timings,
    )


__all__ = ["stream_audio_from_queue", "perform_fallback_buffered_stream"]
