"""Video generation and extension logic."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from features.chat.workflow_runtime import WorkflowRuntime
    from infrastructure.aws.storage import StorageService

from core.exceptions import (
    ConfigurationError,
    ProviderError,
    ServiceError,
    ValidationError,
)
from core.providers.factory import get_video_provider

from .helpers import (
    extract_video_settings,
    build_provider_kwargs,
    build_metadata,
    upload_video_to_s3,
    validate_generation_params,
    validate_extension_params,
)

logger = logging.getLogger(__name__)


async def generate_video(
    *,
    prompt: str,
    settings: Dict[str, Any],
    customer_id: int,
    storage_service: "StorageService",
    input_image_url: str | None = None,
    save_to_s3: bool = True,
    runtime: "WorkflowRuntime" | None = None,
) -> Dict[str, Any]:
    """Generate a video and optionally persist it to S3."""
    validate_generation_params(prompt, customer_id)

    settings = settings or {}

    try:
        provider = get_video_provider(settings)
    except ConfigurationError:
        raise
    except Exception as exc:
        logger.error("Unexpected error resolving video provider: %s", exc)
        raise ConfigurationError(
            f"Unable to resolve video provider: {exc}", key="video.model"
        ) from exc

    video_settings = extract_video_settings(settings)
    provider_name = getattr(provider, "provider_name", "").lower()
    provider_kwargs = build_provider_kwargs(video_settings, provider_name)

    logger.info(
        "Starting video generation (customer=%s, model=%s, aspect_ratio=%s, duration=%ss)",
        customer_id,
        video_settings["model"],
        video_settings["aspect_ratio"],
        video_settings["duration"],
    )

    try:
        if input_image_url:
            video_bytes = await provider.generate_from_image(
                prompt=prompt,
                image_url=input_image_url,
                runtime=runtime,
                **provider_kwargs,
            )
            mode = "image_to_video"
            logger.info(
                "Video provider %s running in image_to_video mode (customer=%s)",
                provider.__class__.__name__,
                customer_id,
            )
        else:
            video_bytes = await provider.generate(
                prompt=prompt,
                model=video_settings["model"],
                runtime=runtime,
                **provider_kwargs,
            )
            mode = "text_to_video"
            logger.info(
                "Video provider %s running in text_to_video mode (customer=%s)",
                provider.__class__.__name__,
                customer_id,
            )
    except NotImplementedError:
        raise
    except ValidationError:
        raise
    except ProviderError:
        raise
    except Exception as exc:
        logger.error("Unexpected video provider failure: %s", exc)
        raise ProviderError(
            f"Failed to generate video: {exc}",
            provider=getattr(provider, "provider_name", "video"),
            original_error=exc,
        ) from exc

    if not video_bytes:
        raise ProviderError("Video provider returned empty payload", provider=getattr(provider, "provider_name", "video"))

    video_url: str | None = None
    if save_to_s3:
        video_url = await upload_video_to_s3(
            storage_service, video_bytes, customer_id, video_settings["file_extension"]
        )
    else:
        logger.info(
            "Skipping S3 upload for video (customer=%s, save_to_s3=%s)",
            customer_id,
            save_to_s3,
        )

    metadata = build_metadata(video_settings, getattr(provider, "provider_name", "video"), mode)

    result: Dict[str, Any] = {
        "video_url": video_url,
        "model": video_settings["model"],
        "duration": video_settings["duration"],
        "settings": metadata,
    }

    if not video_url:
        result["video_bytes"] = video_bytes

    return result


async def extend_video(
    *,
    video_id: str,
    storage_service: "StorageService",
    prompt: str | None = None,
    settings: Dict[str, Any] | None = None,
    customer_id: int = 0,
    save_to_s3: bool = True,
) -> Dict[str, Any]:
    """Extend existing video."""
    validate_extension_params(video_id, customer_id)

    settings = settings or {}

    provider = get_video_provider(settings)

    if not hasattr(provider, "extend_video"):
        raise NotImplementedError(
            f"Provider {provider.provider_name} does not support video extension"
        )

    provider_kwargs = settings.get("video", {})

    video_bytes = await provider.extend_video(
        video_id=video_id, prompt=prompt, **provider_kwargs
    )

    if save_to_s3:
        video_url = await upload_video_to_s3(storage_service, video_bytes, customer_id)
    else:
        import base64
        video_b64 = base64.b64encode(video_bytes).decode("utf-8")
        video_url = f"data:video/mp4;base64,{video_b64}"

    return {
        "video_url": video_url,
        "provider": provider.provider_name,
        "mode": "video_extension",
        "source_video_id": video_id,
        "settings": settings,
    }
