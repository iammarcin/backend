"""Multi-image-to-video generation for KlingAI."""

import logging
from typing import List, Optional, Any

from config.video.providers import klingai as klingai_config
from core.exceptions import ConfigurationError, ProviderError
from .validators_basic import (
    validate_model,
    validate_mode,
    validate_duration,
    validate_aspect_ratio,
    get_mode_for_model,
)
from .validators_image import process_image_input

logger = logging.getLogger(__name__)


async def generate_multi_image_to_video(
    provider,
    prompt: str,
    image_urls: List[str],
    model: Optional[str] = None,
    **kwargs
) -> bytes:
    """
    Generate video from multiple images.

    Args:
        provider: KlingAIVideoProvider instance
        prompt: Text description (max 2500 chars, REQUIRED)
        image_urls: List of 2-4 image URLs or Base64 strings
        model: Model name (default: kling-v1-6, only v1-6 supported)
        **kwargs: Additional parameters:
            - negative_prompt: str (max 2500 chars)
            - mode: str ('std' or 'pro')
            - duration_seconds: int (5 or 10)
            - aspect_ratio: str ('16:9', '9:16', or '1:1')
            - callback_url: str (optional)
            - external_task_id: str (optional)

    Returns:
        Video bytes

    Raises:
        ConfigurationError: Invalid parameters
        ProviderError: API errors, task failures

    Note:
        - Prompt is REQUIRED (unlike single image-to-video)
        - Only kling-v1-6 model is currently supported
        - Images should be pre-cropped to subjects
        - All images should have compatible aspect ratios
    """
    # Validate prompt (required for multi-image)
    if not prompt or len(prompt.strip()) == 0:
        raise ConfigurationError("Prompt is required for multi-image generation")
    if len(prompt) > 2500:
        raise ConfigurationError("Prompt cannot exceed 2500 characters")

    # Validate image list
    if not image_urls:
        raise ConfigurationError("image_urls cannot be empty")

    if len(image_urls) < 2:
        raise ConfigurationError(
            f"At least 2 images required, got {len(image_urls)}"
        )

    if len(image_urls) > 4:
        raise ConfigurationError(
            f"Maximum 4 images allowed, got {len(image_urls)}"
        )

    # Get and validate model (only kling-v1-6 supported)
    model = model or "kling-v1-6"
    if model != "kling-v1-6":
        logger.warning(
            f"Model '{model}' may not be supported for multi-image generation. "
            "Using kling-v1-6"
        )
        model = "kling-v1-6"

    # Extract parameters
    negative_prompt = kwargs.get("negative_prompt")
    if negative_prompt and len(negative_prompt) > 2500:
        raise ConfigurationError(
            "Negative prompt cannot exceed 2500 characters"
        )

    requested_mode = validate_mode(provider, kwargs.get("mode", klingai_config.DEFAULT_MODE))
    mode = get_mode_for_model(model, requested_mode)

    duration = validate_duration(
        provider,
        kwargs.get("duration_seconds", klingai_config.DEFAULT_DURATION),
    )

    aspect_ratio = validate_aspect_ratio(
        provider,
        kwargs.get("aspect_ratio", klingai_config.DEFAULT_ASPECT_RATIO),
    )

    # Process images
    processed_images = []
    for idx, image_url in enumerate(image_urls):
        try:
            processed_image = process_image_input(image_url)
            processed_images.append({"image": processed_image})
        except Exception as e:
            raise ConfigurationError(
                f"Error processing image #{idx}: {str(e)}"
            ) from e

    # Build payload
    payload = {
        "model_name": model,
        "image_list": processed_images,
        "prompt": prompt,
        "mode": mode,
        "duration": str(duration),
        "aspect_ratio": aspect_ratio,
    }

    # Add optional parameters
    if negative_prompt:
        payload["negative_prompt"] = negative_prompt

    if "callback_url" in kwargs:
        payload["callback_url"] = kwargs["callback_url"]

    if "external_task_id" in kwargs:
        payload["external_task_id"] = kwargs["external_task_id"]

    logger.info(
        f"Creating multi-image-to-video task: {len(image_urls)} images, "
        f"model={model}, mode={mode}, duration={duration}s, "
        f"aspect_ratio={aspect_ratio}"
    )

    try:
        # Create task
        task_id = await provider.client.create_task(
            endpoint="/v1/videos/multi-image2video",
            payload=payload
        )

        logger.info(f"Task created: {task_id}")

        # Poll until complete
        task_result = await provider.client.poll_until_complete(
            endpoint="/v1/videos/multi-image2video",
            task_id=task_id,
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
        logger.error(f"Multi-image-to-video generation failed: {str(e)}")
        raise
