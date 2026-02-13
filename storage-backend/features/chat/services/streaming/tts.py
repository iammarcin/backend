"""Helpers for optional TTS streaming of generated chat responses."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from core.exceptions import ProviderError, ServiceError, ValidationError
from core.streaming.manager import StreamingManager
from features.tts.schemas.requests import TTSUserSettings
from features.tts.service import TTSService
from pydantic import ValidationError as PydanticValidationError

logger = logging.getLogger(__name__)


async def maybe_stream_tts(
    *,
    text_response: str,
    settings: Dict[str, Any],
    customer_id: int,
    manager: StreamingManager,
    timings: Dict[str, float],
    tts_service: TTSService,
) -> Optional[Dict[str, Any]]:
    """Stream text-to-speech audio when auto execute is enabled.

    NOTE: Parallel streaming uses :class:`TTSOrchestrator` to pre-compute
    metadata before this function runs.  In that scenario this function is
    skipped entirely and the orchestrated metadata is passed directly to the
    payload builder.  The sequential fallback below remains for backward
    compatibility when TTS auto execution is disabled or settings validation
    fails.
    """

    tts_settings = settings.get("tts") if isinstance(settings, dict) else None
    if not isinstance(tts_settings, dict):
        return None

    auto_execute = bool(tts_settings.get("tts_auto_execute"))
    streaming_enabled = tts_settings.get("streaming")
    if not auto_execute or streaming_enabled is False:
        return None

    payload = {
        "general": settings.get("general", {}),
        "tts": tts_settings,
    }

    try:
        user_settings = TTSUserSettings.model_validate(payload)
    except PydanticValidationError as exc:
        logger.warning(
            "Skipping TTS streaming due to invalid settings (customer=%s): %s",
            customer_id,
            exc,
        )
        return None

    if not text_response.strip():
        return None

    timings["tts_request_sent_time"] = time.time()

    try:
        metadata = await tts_service.stream_text(
            text=text_response,
            customer_id=customer_id,
            user_settings=user_settings,
            manager=manager,
            timings=timings,
        )
    except (ValidationError, ProviderError, ServiceError) as exc:
        logger.error(
            "TTS streaming failed (customer=%s): %s",
            customer_id,
            exc,
        )
        return None

    return {
        "provider": metadata.provider,
        "model": metadata.model,
        "voice": metadata.voice,
        "format": metadata.format,
        "text_chunk_count": metadata.text_chunk_count,
        "audio_chunk_count": metadata.audio_chunk_count,
        "audio_file_url": metadata.audio_file_url,
        "storage_metadata": metadata.storage_metadata,
    }
