"""Utility helpers that encapsulate streaming-oriented behaviour.

The original `TTSService.stream_text` method mixed transport events, error
handling, and timing updates in-line. By isolating this behaviour we keep the
service slimmer and make the streaming flow easier to read and test
independently.
"""

from __future__ import annotations

import base64
import logging
import time
from typing import Any, Dict, Iterable, Tuple

from core.exceptions import ProviderError, ServiceError
from core.streaming.manager import StreamingManager

from .service_models import TTSStreamingMetadata


logger = logging.getLogger(__name__)


def _is_elevenlabs_provider(provider: Any) -> bool:
    """Check if provider is ElevenLabs that supports WebSocket streaming."""

    return (
        hasattr(provider, "name")
        and getattr(provider, "name") == "elevenlabs"
        and hasattr(provider, "stream_websocket")
    )


async def _stream_audio_chunks(
    *,
    manager: StreamingManager,
    provider: Any,
    requests: Iterable[Any],
    audio_format: str,
    text_chunk_total: int,
    timings: Dict[str, float],
    audio_accumulator: bytearray,
    chunk_length_schedule: list[int] | None = None,
    runtime=None,
) -> int:
    """Iterate provider responses, streaming encoded audio via the manager.

    For ElevenLabs provider, uses WebSocket streaming for better progressive
    delivery. For other providers, continues to use standard REST streaming.
    """

    audio_chunk_count = 0
    first_chunk_recorded = False

    use_websocket = _is_elevenlabs_provider(provider)
    if use_websocket:
        logger.debug("Using ElevenLabs WebSocket streaming for real-time audio delivery")

    for tts_request in requests:
        if use_websocket:
            stream_iterator = provider.stream_websocket(
                tts_request, chunk_length_schedule=chunk_length_schedule, runtime=runtime
            )
        else:
            stream_iterator = provider.stream(tts_request)

        async for audio_chunk in stream_iterator:
            if not audio_chunk:
                continue
            if not first_chunk_recorded:
                timings["tts_first_response_time"] = time.time()
                first_chunk_recorded = True
            audio_chunk_count += 1
            encoded = base64.b64encode(audio_chunk).decode()
            audio_accumulator.extend(audio_chunk)
            manager.collect_chunk(encoded, "audio")
            await manager.send_to_queues({"type": "audio_chunk", "content": encoded})

    return audio_chunk_count


async def stream_requests(
    *,
    manager: StreamingManager,
    provider: Any,
    requests: Iterable[Any],
    metadata_provider: str,
    resolved_model: str | None,
    resolved_voice: str | None,
    resolved_format: str,
    timings: Dict[str, float],
    chunk_length_schedule: list[int] | None = None,
    runtime=None,
) -> Tuple[TTSStreamingMetadata, bytes]:
    """Handle the full streaming lifecycle and return session metadata."""

    requests = list(requests)

    if not requests:
        raise ServiceError("No TTS chunks to process")

    text_chunk_total = len(requests)

    start_content = {
        "provider": metadata_provider,
        "model": resolved_model,
        "voice": resolved_voice,
        "format": resolved_format,
        "text_chunk_count": text_chunk_total,
    }

    await manager.send_to_queues(
        {
            "type": "tts_started",
            "content": start_content,
        }
    )

    try:
        audio_accumulator = bytearray()
        audio_chunk_count = await _stream_audio_chunks(
            manager=manager,
            provider=provider,
            requests=requests,
            audio_format=resolved_format,
            text_chunk_total=text_chunk_total,
            timings=timings,
            audio_accumulator=audio_accumulator,
            chunk_length_schedule=chunk_length_schedule,
            runtime=runtime,
        )
    except ProviderError:
        await manager.send_to_queues(
            {
                "type": "tts_error",
                "content": {
                    "message": "TTS provider error",
                    "provider": metadata_provider,
                },
            }
        )
        # Send tts_completed so client doesn't hang waiting for completion signal
        await manager.send_to_queues({"type": "tts_completed", "content": ""})
        raise
    except Exception as exc:  # pylint: disable=broad-except
        await manager.send_to_queues(
            {
                "type": "tts_error",
                "content": {
                    "message": str(exc),
                    "provider": metadata_provider,
                },
            }
        )
        # Send tts_completed so client doesn't hang waiting for completion signal
        await manager.send_to_queues({"type": "tts_completed", "content": ""})
        raise ServiceError(f"TTS streaming failed: {exc}") from exc

    if audio_chunk_count == 0:
        await manager.send_to_queues(
            {
                "type": "tts_error",
                "content": {
                    "message": "No audio produced",
                    "provider": metadata_provider,
                },
            }
        )
        # Send tts_completed so client doesn't hang waiting for completion signal
        await manager.send_to_queues({"type": "tts_completed", "content": ""})
        raise ServiceError("TTS provider returned no audio chunks")

    await manager.send_to_queues(
        {
            "type": "tts_generation_completed",
            "content": {
                "provider": metadata_provider,
                "model": resolved_model,
                "voice": resolved_voice,
                "format": resolved_format,
                "audio_chunk_count": audio_chunk_count,
                "text_chunk_count": text_chunk_total,
            },
        }
    )
    await manager.send_to_queues({"type": "tts_completed", "content": ""})

    metadata = TTSStreamingMetadata(
        provider=metadata_provider,
        model=resolved_model,
        voice=resolved_voice,
        format=resolved_format,
        text_chunk_count=text_chunk_total,
        audio_chunk_count=audio_chunk_count,
    )
    timings["tts_response_time"] = time.time()
    return metadata, bytes(audio_accumulator)


__all__ = ["stream_requests"]
