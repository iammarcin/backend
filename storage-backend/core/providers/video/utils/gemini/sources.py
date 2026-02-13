"""Source asset helpers for Gemini video generation."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from google.genai import types  # type: ignore

from core.exceptions import ProviderError, ValidationError

from . import assets

logger = logging.getLogger(__name__)


async def fetch_image_for_video(image_url: str, *, provider_name: str) -> types.Image:
    """Fetch and prepare an image for Gemini image-to-video requests.

    Returns a types.Image object ready to be passed to generate_videos().
    """

    if not image_url:
        raise ProviderError(
            "Image URL is required for image-to-video",
            provider=provider_name,
        )

    try:
        image_bytes, mime_type = await asyncio.to_thread(assets.fetch_image_bytes, image_url)
    except ValidationError:
        raise
    except ValueError as exc:
        logger.warning("Invalid %s input image: %s", provider_name, exc)
        raise ValidationError(str(exc)) from exc
    except Exception as exc:  # pragma: no cover - network path guard
        logger.error("Failed to fetch input image: %s", exc)
        raise ProviderError(
            f"Failed to download input image: {exc}",
            provider=provider_name,
            original_error=exc,
        ) from exc

    # Validate image can be loaded with PIL
    try:
        await asyncio.to_thread(assets.load_image, image_bytes)
    except ValidationError:
        raise
    except ValueError as exc:
        logger.warning("Invalid %s input image format: %s", provider_name, exc)
        raise ValidationError(str(exc)) from exc
    except Exception as exc:  # pragma: no cover - PIL parsing failures
        logger.error("Failed to parse input image: %s", exc)
        raise ProviderError(
            f"Failed to parse input image: {exc}",
            provider=provider_name,
            original_error=exc,
        ) from exc

    # Detect MIME type if not provided
    if not mime_type:
        mime_type = assets._detect_mime_type(image_bytes)

    # Return types.Image object for the API
    logger.debug(
        "Creating types.Image for video generation: mime_type=%s, bytes_length=%d",
        mime_type,
        len(image_bytes),
    )
    return types.Image(image_bytes=image_bytes, mime_type=mime_type)


__all__ = ["fetch_image_for_video"]
