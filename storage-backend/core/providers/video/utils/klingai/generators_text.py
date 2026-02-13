"""Text-to-video generation for KlingAI."""

import logging
from typing import Optional, Any

from config.video.providers import klingai as klingai_config
from core.exceptions import ConfigurationError, ProviderError
from .validators_basic import (
    validate_model,
    validate_duration,
    validate_aspect_ratio,
    validate_mode,
    supports_cfg_scale,
    supports_audio_generation,
    get_mode_for_model,
)
from .builders import build_camera_control

logger = logging.getLogger(__name__)


async def generate_text_to_video(
    provider,
    prompt: str,
    model: Optional[str] = None,
    runtime: Any = None,
    **kwargs
) -> bytes:
    """
    Generate video from text prompt.

    Args:
        provider: KlingAIVideoProvider instance
        prompt: Text description (max 2500 chars)
        model: Model name (default: kling-v1)
        **kwargs: Additional parameters:
            - negative_prompt: str (max 2500 chars)
            - cfg_scale: float [0, 1] (v1 models only)
            - mode: str ('std' or 'pro')
            - duration_seconds: int (5 or 10)
            - aspect_ratio: str ('16:9', '9:16', or '1:1')
            - camera_control: dict
            - enable_audio: bool (V2.6/O1 models only - generates synchronized audio)
            - callback_url: str (optional)
            - external_task_id: str (optional)

    Returns:
        Video bytes

    Raises:
        ConfigurationError: Invalid parameters
        ProviderError: API errors, task failures

    Note:
        V2.6 models support native audio generation with synchronized dialogue,
        sound effects, and ambient sounds. Use enable_audio=True to activate.
    """
    # Validate prompt
    if not prompt or len(prompt.strip()) == 0:
        raise ConfigurationError("Prompt cannot be empty")
    if len(prompt) > 2500:
        raise ConfigurationError("Prompt cannot exceed 2500 characters")

    # Get and validate model
    model = model or provider.default_model
    model = validate_model(provider, model)

    # Extract and validate parameters
    negative_prompt = kwargs.get("negative_prompt")
    if negative_prompt and len(negative_prompt) > 2500:
        raise ConfigurationError(
            "Negative prompt cannot exceed 2500 characters"
        )

    cfg_scale = kwargs.get("cfg_scale", 0.5)
    if not (0 <= cfg_scale <= 1):
        raise ConfigurationError("cfg_scale must be between 0 and 1")

    # Check if cfg_scale is supported by model
    if model.startswith("kling-v2"):
        if "cfg_scale" in kwargs:
            logger.warning(
                f"cfg_scale not supported by {model}, ignoring parameter"
            )
        cfg_scale = None

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

    # Build request payload
    payload = {
        "model_name": model,
        "prompt": prompt,
        "mode": mode,
        "duration": str(duration),
        "aspect_ratio": aspect_ratio,
    }

    # Add optional parameters
    if negative_prompt:
        payload["negative_prompt"] = negative_prompt

    if cfg_scale is not None:
        payload["cfg_scale"] = cfg_scale

    # Handle camera control
    camera_control = kwargs.get("camera_control")
    if camera_control:
        payload["camera_control"] = build_camera_control(camera_control)

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

    # Optional tracking
    if "callback_url" in kwargs:
        payload["callback_url"] = kwargs["callback_url"]

    if "external_task_id" in kwargs:
        payload["external_task_id"] = kwargs["external_task_id"]

    logger.info(
        f"Creating text-to-video task: model={model}, mode={mode}, "
        f"duration={duration}s, aspect_ratio={aspect_ratio}, "
        f"mode_in_payload={'mode' in payload}, payload_keys={list(payload.keys())}"
    )

    try:
        # Create task
        task_id = await provider.client.create_task(
            endpoint="/v1/videos/text2video",
            payload=payload
        )

        logger.info(f"Task created: {task_id}")

        # Poll until complete
        task_result = await provider.client.poll_until_complete(
            endpoint="/v1/videos/text2video",
            task_id=task_id,
            runtime=runtime,
        )

        # Extract video URL
        videos = task_result.get("videos", [])
        if not videos:
            raise ProviderError("No videos in task result")

        video_url = videos[0].get("url")
        if not video_url:
            raise ProviderError("No video URL in task result")

        logger.info(f"Video generated: {video_url}")

        # Download video
        video_bytes = await provider.client.download_video(video_url)

        logger.info(f"Video downloaded: {len(video_bytes)} bytes")

        return video_bytes

    except Exception as e:
        logger.error(f"Text-to-video generation failed: {str(e)}")
        raise
