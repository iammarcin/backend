"""Operational helpers for Gemini video generation."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from google.genai import types  # type: ignore

from core.exceptions import ProviderError

logger = logging.getLogger(__name__)


async def execute_generation(
    client: Any,
    *,
    prompt: str,
    model: str,
    config: types.GenerateVideosConfig,
    poll_interval: int,
    timeout: int,
    image: Any | None = None,
    runtime: Any = None,
) -> bytes:
    """Submit a Gemini generation request and return the resulting bytes."""

    request_kwargs = {
        "model": model,
        "prompt": prompt,
        "config": config,
    }
    if image is not None:
        request_kwargs["image"] = image

    try:
        operation = await asyncio.to_thread(
            client.models.generate_videos,
            **request_kwargs,
        )
    except ProviderError:
        raise
    except Exception as exc:  # pragma: no cover - defensive provider guard
        logger.error("Gemini video generation request failed: %s", exc, exc_info=True)
        raise ProviderError(
            f"Gemini video generation failed: {exc}",
            provider="gemini_video",
            original_error=exc,
        ) from exc

    return await poll_operation(
        client,
        operation,
        poll_interval=poll_interval,
        timeout=timeout,
        runtime=runtime,
    )


async def poll_operation(
    client: Any,
    operation: Any,
    *,
    poll_interval: int,
    timeout: int,
    runtime: Any = None,
) -> bytes:
    """Poll a long-running Gemini operation until completion."""

    start_time = time.monotonic()
    current_operation = operation

    while not getattr(current_operation, "done", False):
        elapsed = time.monotonic() - start_time
        if elapsed > timeout:
            raise ProviderError(
                "Video generation timed out after 10 minutes",
                provider="gemini_video",
            )

        # Check for cancellation
        if runtime and runtime.is_cancelled():
            logger.info("Gemini video generation cancelled")
            raise asyncio.CancelledError("Video generation cancelled by user")

        logger.debug(
            "Gemini video generation pending (elapsed %.1fs)",
            elapsed,
        )

        await asyncio.sleep(poll_interval)
        current_operation = await asyncio.to_thread(
            client.operations.get,
            current_operation,
        )

    logger.info("Gemini video generation operation completed")

    generated_videos = getattr(current_operation.response, "generated_videos", None)
    if not generated_videos:
        raise ProviderError("No videos generated", provider="gemini_video")

    return await download_video_asset(client, generated_videos[0])


async def download_video_asset(client: Any, generated_video: Any) -> bytes:
    """Download the binary payload for a generated Gemini video."""

    video_asset = getattr(generated_video, "video", None) or getattr(
        generated_video, "media", None
    )

    video_bytes = None

    try:
        if video_asset is not None:
            # Download the video file
            await asyncio.to_thread(
                client.files.download,
                file=video_asset,
            )

            # After download, the bytes should be in video_asset.video_bytes
            # Try multiple ways to get the video bytes
            video_bytes = getattr(video_asset, "video_bytes", None)
            if video_bytes is None:
                video_bytes = getattr(video_asset, "bytes", None)
            if video_bytes is None:
                video_bytes = getattr(video_asset, "data", None)
            if video_bytes is None and hasattr(video_asset, "read"):
                video_bytes = video_asset.read()
        else:
            video_bytes = getattr(generated_video, "video_bytes", None)

    except Exception as exc:  # pragma: no cover - provider failure guard
        logger.error("Failed to download generated video: %s", exc, exc_info=True)
        raise ProviderError(
            f"Failed to download generated video: {exc}",
            provider="gemini_video",
            original_error=exc,
        ) from exc

    # Additional fallbacks
    if video_bytes is None and hasattr(generated_video, "bytes"):
        video_bytes = generated_video.bytes
    if video_bytes is None and hasattr(generated_video, "data"):
        video_bytes = generated_video.data

    # Handle memoryview
    if isinstance(video_bytes, memoryview):
        video_bytes = video_bytes.tobytes()

    if not video_bytes:
        logger.error(
            "No video bytes found. generated_video attributes: %s, video_asset attributes: %s",
            dir(generated_video) if generated_video else None,
            dir(video_asset) if video_asset else None,
        )
        raise ProviderError("Failed to download generated video", provider="gemini_video")

    logger.info("Successfully extracted video bytes (%d bytes)", len(video_bytes))
    return bytes(video_bytes)


__all__ = ["download_video_asset", "execute_generation", "poll_operation"]
