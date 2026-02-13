"""Helper functions for video service operations."""

import logging
from typing import Any, Dict, Optional

from core.exceptions import ValidationError
from infrastructure.aws.storage import StorageService

logger = logging.getLogger(__name__)


def extract_video_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    """Extract video-specific settings from configuration."""
    video_settings = settings.get("video", {}) if isinstance(settings, dict) else {}

    return {
        "model": str(video_settings.get("model", "veo-3.1-fast")),
        "duration": int(video_settings.get("duration_seconds", 5)),
        "aspect_ratio": str(video_settings.get("aspect_ratio", "9:16")),
        "person_generation": video_settings.get("person_generation"),
        "enhance_prompt": video_settings.get("enhance_prompt", True),
        "number_of_videos": video_settings.get("number_of_videos", 1),
        "file_extension": str(video_settings.get("file_extension", "mp4")),
        "fps": video_settings.get("fps"),
        "resolution": video_settings.get("resolution"),
        "generate_audio": video_settings.get("generate_audio"),
        "compression_quality": video_settings.get("compression_quality"),
        "reference_images": video_settings.get("reference_images"),
        "last_frame": video_settings.get("last_frame"),
        "mask": video_settings.get("mask"),
        "negative_prompt": video_settings.get("negative_prompt"),
    }


def build_provider_kwargs(video_settings: Dict[str, Any], provider_name: str) -> Dict[str, Any]:
    """Build provider-specific kwargs from video settings."""
    kwargs = {
        "duration_seconds": video_settings["duration"],
        "aspect_ratio": video_settings["aspect_ratio"],
        "person_generation": video_settings["person_generation"],
        "enhance_prompt": video_settings["enhance_prompt"],
        "number_of_videos": video_settings["number_of_videos"],
    }

    if provider_name.lower() == "openai":
        poll_timeout = video_settings.get("poll_timeout_seconds")
        poll_interval = video_settings.get("poll_interval_seconds")

        if poll_timeout is not None:
            try:
                poll_timeout_seconds = max(int(poll_timeout), 1)
            except (TypeError, ValueError):
                logger.warning(
                    "Invalid poll_timeout_seconds value %r; falling back to default",
                    poll_timeout,
                )
            else:
                kwargs["poll_timeout_seconds"] = poll_timeout_seconds

        if poll_interval is not None:
            try:
                poll_interval_seconds = max(float(poll_interval), 0.1)
            except (TypeError, ValueError):
                logger.warning(
                    "Invalid poll_interval_seconds value %r; falling back to default",
                    poll_interval,
                )
            else:
                kwargs["poll_interval_seconds"] = poll_interval_seconds

    # Add optional parameters
    optional_params = [
        "fps", "resolution", "generate_audio", "compression_quality",
        "reference_images", "last_frame", "mask", "negative_prompt"
    ]

    for param in optional_params:
        if video_settings.get(param) is not None:
            kwargs[param] = video_settings[param]

    return kwargs


def build_metadata(video_settings: Dict[str, Any], provider_name: str, mode: str) -> Dict[str, Any]:
    """Build metadata dictionary for video generation."""
    metadata = {
        "provider": provider_name,
        "model": video_settings["model"],
        "aspect_ratio": video_settings["aspect_ratio"],
        "duration_seconds": video_settings["duration"],
        "mode": mode,
        "enhance_prompt": bool(video_settings["enhance_prompt"]),
        "number_of_videos": int(video_settings["number_of_videos"] or 1),
    }

    if video_settings["person_generation"]:
        metadata["person_generation"] = video_settings["person_generation"]

    optional_metadata = [
        "fps", "resolution", "generate_audio", "compression_quality",
        "reference_images", "last_frame", "mask", "negative_prompt"
    ]

    for param in optional_metadata:
        if video_settings.get(param) is not None:
            metadata[param] = video_settings[param]

    return metadata


async def upload_video_to_s3(
    storage_service: StorageService,
    video_bytes: bytes,
    customer_id: int,
    file_extension: str = "mp4"
) -> str:
    """Upload video to S3 and return URL."""
    try:
        video_url = await storage_service.upload_video(
            video_bytes=video_bytes,
            customer_id=customer_id,
            file_extension=file_extension,
        )
        return video_url
    except Exception as exc:
        from core.exceptions import ServiceError
        logger.error("Unexpected storage failure: %s", exc)
        raise ServiceError(f"Failed to upload video: {exc}") from exc


def validate_generation_params(prompt: str, customer_id: int) -> None:
    """Validate common generation parameters."""
    if not prompt or not prompt.strip():
        raise ValidationError("Prompt cannot be empty", field="prompt")
    if customer_id <= 0:
        raise ValidationError("Invalid customer_id", field="customer_id")


def validate_extension_params(video_id: str, customer_id: int) -> None:
    """Validate video extension parameters."""
    if not video_id:
        raise ValidationError("video_id is required", field="video_id")
    if customer_id <= 0:
        raise ValidationError("customer_id must be positive", field="customer_id")
