"""Persistence helpers for TTS service orchestration."""

from __future__ import annotations

import base64
from typing import Any, Callable, Dict, Tuple

from infrastructure.aws.storage import StorageService

from features.tts.schemas.requests import TTSUserSettings
from features.tts.utils import prepare_audio_payload


async def persist_audio_and_metadata(
    *,
    storage_service_factory: "Callable[[], StorageService]",
    audio_bytes: bytes,
    user_settings: TTSUserSettings,
    customer_id: int,
    provider_name: str,
    resolved_model: str | None,
    resolved_voice: str | None,
    resolved_format: str,
    chunk_count: int,
    extra_metadata: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    """Store audio if required and assemble the metadata payload."""

    (
        prepared_audio,
        storage_format,
        content_type,
        format_metadata,
    ) = prepare_audio_payload(audio_bytes, resolved_format)

    extra: Dict[str, Any] = dict(extra_metadata or {})
    if format_metadata:
        extra.update(format_metadata)

    metadata: Dict[str, Any] = {
        "provider": provider_name,
        "model": resolved_model,
        "voice": resolved_voice,
        "format": storage_format,
        "chunk_count": chunk_count,
        "extra": extra or None,
    }
    if resolved_format and resolved_format != storage_format:
        metadata["original_format"] = resolved_format

    if user_settings.general.save_to_s3:
        storage_service = storage_service_factory()
        s3_url = await storage_service.upload_audio(
            audio_bytes=prepared_audio,
            customer_id=customer_id,
            file_extension=storage_format,
            content_type=content_type,
        )
        metadata["s3_url"] = s3_url
        metadata["extra"] = extra or None
        return s3_url, metadata

    encoded = base64.b64encode(prepared_audio).decode()
    inline_url = f"data:{content_type};base64,{encoded}"
    extra["inline_payload_bytes"] = len(prepared_audio)
    metadata["extra"] = extra
    return inline_url, metadata


__all__ = ["persist_audio_and_metadata"]
