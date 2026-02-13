"""Generate-flow helpers for the TTS service."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict

from core.exceptions import ServiceError, ValidationError

from infrastructure.aws.storage import StorageService

from features.tts.schemas.requests import TTSAction, TTSGenerateRequest
from features.tts.utils import merge_audio_chunks

from .request_builder import build_tts_requests
from .service_models import TTSGenerationResult
from .service_persistence import persist_audio_and_metadata
from .test_mode import generate_test_result


logger = logging.getLogger(__name__)


async def generate_audio(
    *,
    request: TTSGenerateRequest,
    provider_resolver: Callable[[Dict[str, Any]], Any],
    storage_service_factory: Callable[[], StorageService],
) -> TTSGenerationResult:
    """Generate audio for the supplied request in a single response."""

    if request.action not in {TTSAction.TTS_NO_STREAM, TTSAction.BILLING}:
        raise ValidationError(f"Unsupported TTS action: {request.action}", field="action")

    if request.action is TTSAction.BILLING:
        raise ValidationError("Billing requests must be handled via `get_billing`", field="action")

    if not request.user_input.text:
        raise ValidationError("Text input is required", field="user_input.text")

    user_settings = request.user_settings
    if user_settings.general.return_test_data:
        logger.info("Returning canned TTS data for customer_id=%s", request.customer_id)
        return generate_test_result(customer_id=request.customer_id, user_settings=user_settings)

    batch = build_tts_requests(
        text=request.user_input.text,
        user_settings=user_settings,
        customer_id=request.customer_id,
        provider_resolver=provider_resolver,
    )

    if not batch.requests:
        raise ServiceError("No TTS chunks to process")

    audio_chunks = []
    last_result: Dict[str, Any] = {}

    resolved_model = batch.model
    resolved_format = batch.format or "mp3"
    resolved_voice = batch.voice

    for tts_request in batch.requests:
        result = await batch.provider.generate(tts_request)
        audio_chunks.append(result.audio_bytes)
        resolved_model = result.model or resolved_model
        resolved_format = result.format or resolved_format
        resolved_voice = result.voice or resolved_voice
        last_result = dict(result.metadata or {})

    merged_audio = merge_audio_chunks(audio_chunks, output_format=resolved_format)
    if not merged_audio:
        raise ServiceError("Provider returned empty audio payload")

    metadata_provider = getattr(batch.provider, "name", "tts")
    result_url, metadata = await persist_audio_and_metadata(
        storage_service_factory=storage_service_factory,
        audio_bytes=merged_audio,
        user_settings=user_settings,
        customer_id=request.customer_id,
        provider_name=metadata_provider,
        resolved_model=resolved_model,
        resolved_voice=resolved_voice,
        resolved_format=resolved_format,
        chunk_count=len(batch.requests),
        extra_metadata=last_result,
    )

    stored_format = metadata.get("format", resolved_format)

    return TTSGenerationResult(
        status="completed",
        result=result_url,
        provider=metadata["provider"],
        model=resolved_model,
        voice=resolved_voice,
        format=stored_format,
        chunk_count=len(batch.requests),
        metadata=metadata,
    )


__all__ = ["generate_audio"]
