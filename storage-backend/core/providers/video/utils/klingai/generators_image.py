"""Image-to-video generation for KlingAI."""

import logging
from typing import Optional, Any

from config.video.providers import klingai as klingai_config
from core.exceptions import ConfigurationError, ProviderError
from .validators_basic import (
    validate_model,
    validate_duration,
    validate_mode,
    supports_cfg_scale,
    supports_audio_generation,
    validate_motion_brush_compatibility,
    get_mode_for_model,
)
from .builders import build_camera_control, build_dynamic_masks
from .validators_image import process_image_input

logger = logging.getLogger(__name__)


async def generate_image_to_video(
    provider,
    prompt: str,
    image_url: str,
    model: Optional[str] = None,
    runtime: Any = None,
    **kwargs
) -> bytes:
    """
    Generate video from image with optional text guidance.

    Args:
        provider: KlingAIVideoProvider instance
        prompt: Text description (max 2500 chars, optional for KlingAI)
        image_url: Reference image URL or Base64
        model: Model name (default: kling-v1)
        **kwargs: Additional parameters:
            - image_tail: str (end frame image URL/Base64)
            - negative_prompt: str (max 2500 chars)
            - cfg_scale: float [0, 1] (v1 models only)
            - mode: str ('std' or 'pro')
            - duration_seconds: int (5 or 10)
            - static_mask: str (static brush mask URL/Base64)
            - dynamic_masks: list (dynamic brush configurations)
            - camera_control: dict (camera movement)
            - enable_audio: bool (V2.6/O1 models only - generates synchronized audio)

    Returns:
        Video bytes

    Raises:
        ConfigurationError: Invalid parameters
        ProviderError: API errors, task failures

    Note:
        - At least one of image_url or image_tail must be provided
        - image+image_tail, motion brush (static_mask/dynamic_masks), and camera_control are mutually exclusive
        - V2.6 models support native audio generation with synchronized audio
    """
    # Validate image
    if not image_url:
        raise ConfigurationError("image_url is required")

    # Get and validate model
    model = model or provider.default_model
    model = validate_model(provider, model)

    # Validate prompt
    if prompt and len(prompt) > 2500:
        raise ConfigurationError("Prompt cannot exceed 2500 characters")

    # Extract parameters
    image_tail = kwargs.get("image_tail")
    negative_prompt = kwargs.get("negative_prompt")
    if negative_prompt and len(negative_prompt) > 2500:
        raise ConfigurationError(
            "Negative prompt cannot exceed 2500 characters"
        )

    # Validate mutually exclusive features
    has_end_frame = image_tail is not None
    has_motion_brush = (
        kwargs.get("static_mask") is not None or
        kwargs.get("dynamic_masks") is not None
    )
    has_camera_control = kwargs.get("camera_control") is not None

    exclusive_count = sum([has_end_frame, has_motion_brush, has_camera_control])
    if exclusive_count > 1:
        raise ConfigurationError(
            "image+image_tail, motion brush (static_mask/dynamic_masks), "
            "and camera_control are mutually exclusive"
        )

    # Validate cfg_scale
    cfg_scale = kwargs.get("cfg_scale", 0.5)
    if not (0 <= cfg_scale <= 1):
        raise ConfigurationError("cfg_scale must be between 0 and 1")

    if model.startswith("kling-v2") and "cfg_scale" in kwargs:
        logger.warning(
            f"cfg_scale not supported by {model}, ignoring parameter"
        )
        cfg_scale = None

    # Get other parameters
    requested_mode = validate_mode(provider, kwargs.get("mode", klingai_config.DEFAULT_MODE))
    mode = get_mode_for_model(model, requested_mode)
    duration = validate_duration(
        provider,
        kwargs.get("duration_seconds", klingai_config.DEFAULT_DURATION),
    )

    # Validate motion brush compatibility
    validate_motion_brush_compatibility(
        model, mode, duration, has_motion_brush
    )

    # Build payload
    payload = {
        "model_name": model,
        "image": process_image_input(image_url),
        "mode": mode,
        "duration": str(duration),
    }

    # Add optional parameters
    if prompt:
        payload["prompt"] = prompt

    if negative_prompt:
        payload["negative_prompt"] = negative_prompt

    if cfg_scale is not None:
        payload["cfg_scale"] = cfg_scale

    if image_tail:
        payload["image_tail"] = process_image_input(image_tail)

    if kwargs.get("static_mask"):
        payload["static_mask"] = process_image_input(kwargs["static_mask"])

    if kwargs.get("dynamic_masks"):
        payload["dynamic_masks"] = build_dynamic_masks(
            kwargs["dynamic_masks"]
        )

    if has_camera_control:
        payload["camera_control"] = build_camera_control(
            kwargs["camera_control"]
        )

    # Handle audio generation (V2.6 and O1 models only)
    enable_audio = kwargs.get("enable_audio", False)
    if enable_audio:
        if supports_audio_generation(model):
            payload["enable_audio"] = True
            logger.info(f"Audio generation enabled for model {model}")
        else:
            logger.warning(
                f"enable_audio requested but {model} doesn't support it. "
                "Audio generation requires V2.6 or O1 models."
            )

    logger.info(
        f"Creating image-to-video task: model={model}, mode={mode}, "
        f"duration={duration}s, has_tail={has_end_frame}, "
        f"has_motion_brush={has_motion_brush}"
    )

    try:
        # Create task
        task_id = await provider.client.create_task(
            endpoint="/v1/videos/image2video",
            payload=payload
        )

        logger.info(f"Task created: {task_id}")

        # Poll until complete
        task_result = await provider.client.poll_until_complete(
            endpoint="/v1/videos/image2video",
            task_id=task_id,
            runtime=runtime,
        )

        # Extract and download video
        videos = task_result.get("videos", [])
        if not videos:
            raise ProviderError("No videos in task result")

        video_url = videos[0].get("url")
        if not video_url:
            raise ProviderError("No video URL in task result")

        logger.info(f"Video generated: {video_url}")

        video_bytes = await provider.client.download_video(video_url)
        logger.info(f"Video downloaded: {len(video_bytes)} bytes")

        return video_bytes

    except Exception as e:
        logger.error(f"Image-to-video generation failed: {str(e)}")
        raise
