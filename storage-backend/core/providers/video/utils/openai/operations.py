"""Operational helpers for the OpenAI Sora provider."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Tuple

try:
    from openai.types.video import Video
except ImportError:
    # Fallback for older OpenAI SDK versions that don't have video types
    Video = Any

from core.exceptions import ProviderError


logger = logging.getLogger(__name__)


async def create_video_job(
    client: Any,
    *,
    prompt: str,
    model: str,
    seconds: str,
    size: str,
    input_reference: Tuple[str, bytes, str] | None = None,
    provider_name: str = "openai_video",
    poll_timeout_seconds: int = 240,
    poll_interval_seconds: float = 5.0,
    runtime: Any = None,
) -> Video:
    """Submit an OpenAI Sora job and wait for completion."""

    params: dict[str, Any] = {
        "prompt": prompt,
        "model": model,
        "seconds": seconds,
        "size": size,
    }
    if input_reference:
        params["input_reference"] = input_reference

    try:
        job = await client.videos.create(**params)
    except Exception as exc:  # pragma: no cover - provider surface
        raise ProviderError(
            f"OpenAI Sora request failed: {exc}",
            provider=provider_name,
            original_error=exc,
        ) from exc

    if isinstance(job, Video) and getattr(job, "status", None) == "completed":
        return job

    video_id = getattr(job, "id", None)
    if not video_id:
        raise ProviderError("OpenAI returned an invalid job identifier", provider=provider_name)

    start_time = time.monotonic()
    last_status = getattr(job, "status", None)

    while True:
        if time.monotonic() - start_time >= poll_timeout_seconds:
            raise ProviderError(
                f"Timed out waiting for OpenAI video (last status={last_status})",
                provider=provider_name,
            )

        # Check for cancellation
        if runtime and runtime.is_cancelled():
            logger.info("OpenAI Sora video cancelled (id=%s)", video_id)

            # Try to cancel via API if available
            try:
                await client.responses.cancel(video_id)
                logger.info("OpenAI Sora video response cancelled via API")
            except Exception as exc:
                logger.warning("Failed to cancel OpenAI Sora response: %s", exc)

            raise asyncio.CancelledError("Video generation cancelled by user")

        try:
            video = await client.videos.retrieve(video_id)
        except Exception as exc:  # pragma: no cover - provider surface
            raise ProviderError(
                f"Failed to poll OpenAI video status: {exc}",
                provider=provider_name,
                original_error=exc,
            ) from exc

        if not isinstance(video, Video):
            raise ProviderError("Unexpected response type from OpenAI", provider=provider_name)

        status = getattr(video, "status", None)
        if status == "completed":
            return video

        if status in {"failed", "cancelled", "canceled"}:
            message = (
                video.error.message
                if getattr(video, "error", None)
                else f"OpenAI video generation {status}"
            )
            raise ProviderError(message, provider=provider_name)

        if status and status != last_status:
            logger.info(
                "OpenAI video %s status update: %s",
                video_id,
                status,
            )
            last_status = status

        await asyncio.sleep(poll_interval_seconds)


async def download_video_bytes(
    client: Any,
    video: Video,
    *,
    provider_name: str = "openai_video",
) -> bytes:
    """Download the MP4 payload for a completed Sora video."""

    try:
        response = await client.videos.download_content(video.id, variant="video")
    except Exception as exc:  # pragma: no cover - provider surface
        raise ProviderError(
            f"Failed to download OpenAI video content: {exc}",
            provider=provider_name,
            original_error=exc,
        ) from exc

    video_bytes = getattr(response, "content", None)
    if not video_bytes and hasattr(response, "aread"):
        video_bytes = await response.aread()

    if not video_bytes:
        raise ProviderError("OpenAI returned empty video payload", provider=provider_name)

    return bytes(video_bytes)


__all__ = ["create_video_job", "download_video_bytes"]
