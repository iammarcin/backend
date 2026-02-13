"""Utilities dedicated to the deterministic TTS test mode.

The service exposes a flag that bypasses providers and returns canned
responses. Extracting these helpers clarifies the intent inside the main
service and lets tests reuse the same logic when stubbing out provider
calls.
"""

from __future__ import annotations

import base64
from typing import Dict

from core.streaming.manager import StreamingManager
from features.tts.schemas.requests import TTSUserSettings

from .service_models import TTSGenerationResult, TTSStreamingMetadata


def build_test_audio_url(customer_id: int) -> str:
    """Return a stable pseudo URL used in canned responses."""

    payload = base64.b64encode(f"tts-test-{customer_id}".encode()).decode()
    return f"https://example.invalid/{customer_id}/assets/tts/{payload}.mp3"


def build_test_metadata(user_settings: TTSUserSettings) -> Dict[str, str | None]:
    """Prepare consistent metadata for canned TTS payloads."""

    return {
        "provider": "test-data",
        "model": user_settings.tts.model or "mock-model",
        "voice": user_settings.tts.voice,
        "format": user_settings.tts.format or "mp3",
    }


def generate_test_result(
    *, customer_id: int, user_settings: TTSUserSettings
) -> TTSGenerationResult:
    """Produce the standard result object for test-mode generation."""

    metadata = build_test_metadata(user_settings)
    metadata.update({"chunk_count": 1, "extra": {"mode": "test"}})

    return TTSGenerationResult(
        status="completed",
        result=build_test_audio_url(customer_id),
        provider="test-data",
        model=metadata["model"],
        voice=metadata["voice"],
        format=metadata["format"],
        chunk_count=1,
        metadata=metadata,
    )


async def emit_test_stream(
    manager: StreamingManager,
    user_settings: TTSUserSettings,
    *,
    customer_id: int = 0,
    completion_token: str | None = None,
) -> TTSStreamingMetadata:
    """Send a canned streaming payload over the provided manager."""

    fake_bytes = base64.b64decode(b"dGVzdC1hdWRpbw==")
    encoded = base64.b64encode(fake_bytes).decode()
    metadata = build_test_metadata(user_settings)
    audio_url = build_test_audio_url(customer_id)

    try:
        await manager.send_to_queues(
            {
                "type": "tts_started",
                "content": {
                    "provider": metadata["provider"],
                    "model": metadata["model"],
                    "voice": metadata["voice"],
                    "format": metadata["format"],
                    "text_chunk_count": 1,
                },
            }
        )
        manager.collect_chunk(encoded, "audio")
        await manager.send_to_queues({"type": "audio_chunk", "content": encoded})
        await manager.send_to_queues({"type": "tts_completed", "content": ""})
        # Send simple tts_file_uploaded event - standardized format for all clients
        await manager.send_to_queues({
            "type": "tts_file_uploaded",
            "content": {"audio_url": audio_url}
        })

        return TTSStreamingMetadata(
            provider=metadata["provider"],
            model=metadata["model"],
            voice=metadata["voice"],
            format=metadata["format"],
            text_chunk_count=1,
            audio_chunk_count=1,
            audio_file_url=audio_url,
            storage_metadata={
                "provider": metadata["provider"],
                "model": metadata["model"],
                "voice": metadata["voice"],
                "format": metadata["format"],
                "audio_chunk_count": 1,
            },
        )
    finally:
        if completion_token:
            await manager.signal_completion(token=completion_token)


__all__ = [
    "build_test_audio_url",
    "build_test_metadata",
    "generate_test_result",
    "emit_test_stream",
]
