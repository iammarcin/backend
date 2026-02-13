"""Video extension generation for KlingAI."""

import logging
from typing import Optional, Dict, Any

from core.exceptions import ConfigurationError, ProviderError

logger = logging.getLogger(__name__)


async def extend_video(
    provider,
    video_id: str,
    prompt: Optional[str] = None,
    **kwargs
) -> bytes:
    """
    Extend existing video by 4-5 seconds.

    Args:
        provider: KlingAIVideoProvider instance
        video_id: ID of video to extend (from KlingAI generation)
        prompt: Optional text guidance for extension (max 2500 chars)
        **kwargs: Additional parameters:
            - negative_prompt: str (max 2500 chars)
            - cfg_scale: float [0, 1]
            - callback_url: str (optional)

    Returns:
        Extended video bytes

    Raises:
        ConfigurationError: Invalid parameters
        ProviderError: API errors, task failures

    Note:
        - Each extension adds 4-5 seconds
        - Total video duration cannot exceed 3 minutes (180s)
        - Extended videos can be extended again (chainable)
        - Videos expire after 30 days (cannot extend expired videos)
        - Model and mode match the source video automatically
    """
    # Validate video_id
    if not video_id or len(video_id.strip()) == 0:
        raise ConfigurationError("video_id is required")

    # Validate prompt
    if prompt and len(prompt) > 2500:
        raise ConfigurationError("Prompt cannot exceed 2500 characters")

    # Extract parameters
    negative_prompt = kwargs.get("negative_prompt")
    if negative_prompt and len(negative_prompt) > 2500:
        raise ConfigurationError(
            "Negative prompt cannot exceed 2500 characters"
        )

    cfg_scale = kwargs.get("cfg_scale", 0.5)
    if not (0 <= cfg_scale <= 1):
        raise ConfigurationError("cfg_scale must be between 0 and 1")

    # Build payload
    payload = {
        "video_id": video_id,
        "cfg_scale": cfg_scale,
    }

    # Add optional parameters
    if prompt:
        payload["prompt"] = prompt

    if negative_prompt:
        payload["negative_prompt"] = negative_prompt

    if "callback_url" in kwargs:
        payload["callback_url"] = kwargs["callback_url"]

    logger.info(
        f"Creating video extension task: video_id={video_id}, "
        f"has_prompt={prompt is not None}"
    )

    try:
        # Create task
        task_id = await provider.client.create_task(
            endpoint="/v1/videos/video-extend",
            payload=payload
        )

        logger.info(f"Extension task created: {task_id}")

        # Poll until complete
        task_result = await provider.client.poll_until_complete(
            endpoint="/v1/videos/video-extend",
            task_id=task_id,
        )

        # Extract video
        videos = task_result.get("videos", [])
        if not videos:
            raise ProviderError("No videos in task result")

        video_url = videos[0].get("url")
        if not video_url:
            raise ProviderError("No video URL in task result")

        extended_duration = videos[0].get("duration", "unknown")

        logger.info(
            f"Video extended: {video_url}, new duration: {extended_duration}s"
        )

        # Download video
        video_bytes = await provider.client.download_video(video_url)
        logger.info(f"Extended video downloaded: {len(video_bytes)} bytes")

        return video_bytes

    except Exception as e:
        logger.error(f"Video extension failed: {str(e)}")
        raise
