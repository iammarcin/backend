"""Avatar video generation for KlingAI."""

import logging
from typing import Optional, Any

from core.exceptions import ConfigurationError, ProviderError
from .validators_image import process_image_input

logger = logging.getLogger(__name__)


# Avatar-specific models
AVATAR_MODELS = ["avatar-standard", "avatar-pro"]


async def generate_avatar_video(
    provider,
    image_url: str,
    text: Optional[str] = None,
    audio_url: Optional[str] = None,
    model: str = "avatar-standard",
    **kwargs
) -> bytes:
    """
    Generate avatar video with lip-sync from face image.

    The Avatar API creates talking head videos by:
    1. Taking a face image as input
    2. Either generating speech from text (TTS) or using provided audio
    3. Synchronizing lip movements with the audio

    Args:
        provider: KlingAIVideoProvider instance
        image_url: Face image URL or Base64 (portrait recommended)
        text: Text for TTS speech generation (mutually exclusive with audio_url)
        audio_url: Custom audio file URL for lip-sync (mutually exclusive with text)
        model: Avatar model ('avatar-standard' or 'avatar-pro')
        **kwargs: Additional parameters:
            - tts_speed: float (0.8-2.0, default: 1.0) - TTS speech speed
            - tts_voice: str - Voice selection for TTS
            - callback_url: str (optional)
            - external_task_id: str (optional)

    Returns:
        Video bytes (1080p @ 48 FPS, up to 1 minute)

    Raises:
        ConfigurationError: Invalid parameters
        ProviderError: API errors, task failures

    Note:
        - Either text OR audio_url must be provided, not both
        - Supports English, Japanese, Korean, Chinese languages
        - Best results with clear frontal face images
        - Audio files: mp3, wav, flac, ogg (max 20MB, 60s)
    """
    # Validate inputs
    if not image_url:
        raise ConfigurationError("image_url is required for avatar generation")

    if not text and not audio_url:
        raise ConfigurationError(
            "Either 'text' (for TTS) or 'audio_url' (for lip-sync) is required"
        )

    if text and audio_url:
        raise ConfigurationError(
            "Cannot use both 'text' and 'audio_url' - they are mutually exclusive"
        )

    # Validate model
    if model not in AVATAR_MODELS:
        raise ConfigurationError(
            f"Invalid avatar model '{model}'. Allowed: {AVATAR_MODELS}"
        )

    # Build payload
    payload = {
        "model_name": model,
        "face_image": process_image_input(image_url),
    }

    # TTS mode
    if text:
        if len(text) > 2500:
            raise ConfigurationError("Text cannot exceed 2500 characters")

        payload["tts_text"] = text

        # TTS speed (0.8-2.0)
        tts_speed = kwargs.get("tts_speed", 1.0)
        if not (0.8 <= tts_speed <= 2.0):
            raise ConfigurationError("tts_speed must be between 0.8 and 2.0")
        payload["tts_speed"] = tts_speed

        # Voice selection
        if "tts_voice" in kwargs:
            payload["tts_timbre"] = kwargs["tts_voice"]

        logger.info(f"Avatar TTS mode: {len(text)} chars, speed={tts_speed}")

    # Custom audio mode
    if audio_url:
        payload["local_dubbing_url"] = audio_url
        logger.info(f"Avatar lip-sync mode: audio_url provided")

    # Optional tracking
    if "callback_url" in kwargs:
        payload["callback_url"] = kwargs["callback_url"]

    if "external_task_id" in kwargs:
        payload["external_task_id"] = kwargs["external_task_id"]

    logger.info(f"Creating avatar task: model={model}")

    try:
        # Create task
        # Note: Avatar API might use different endpoint - adjust as needed
        task_id = await provider.client.create_task(
            endpoint="/v1/videos/avatar",
            payload=payload
        )

        logger.info(f"Avatar task created: {task_id}")

        # Poll until complete
        task_result = await provider.client.poll_until_complete(
            endpoint="/v1/videos/avatar",
            task_id=task_id,
        )

        # Extract video URL
        videos = task_result.get("videos", [])
        if not videos:
            raise ProviderError("No videos in avatar task result")

        video_url = videos[0].get("url")
        if not video_url:
            raise ProviderError("No video URL in avatar task result")

        logger.info(f"Avatar video generated: {video_url}")

        # Download video
        video_bytes = await provider.client.download_video(video_url)
        logger.info(f"Avatar video downloaded: {len(video_bytes)} bytes")

        return video_bytes

    except Exception as e:
        logger.error(f"Avatar generation failed: {str(e)}")
        raise


async def generate_lip_sync(
    provider,
    video_id: str,
    text: Optional[str] = None,
    audio_url: Optional[str] = None,
    **kwargs
) -> bytes:
    """
    Add lip-sync to an existing generated video.

    This modifies a previously generated video to add lip-synchronized
    speech, either from TTS text or custom audio.

    Args:
        provider: KlingAIVideoProvider instance
        video_id: ID of the source video (from text2video or image2video)
        text: Text for TTS speech generation
        audio_url: Custom audio file URL for lip-sync
        **kwargs: Additional parameters:
            - tts_speed: float (0.8-2.0) - TTS speech speed
            - tts_voice: str - Voice selection for TTS
            - callback_url: str (optional)

    Returns:
        Video bytes with lip-sync applied

    Raises:
        ConfigurationError: Invalid parameters
        ProviderError: API errors, task failures
    """
    if not video_id:
        raise ConfigurationError("video_id is required for lip-sync")

    if not text and not audio_url:
        raise ConfigurationError(
            "Either 'text' (for TTS) or 'audio_url' (for lip-sync) is required"
        )

    if text and audio_url:
        raise ConfigurationError(
            "Cannot use both 'text' and 'audio_url' - they are mutually exclusive"
        )

    # Build payload
    payload = {
        "origin_task_id": video_id,
    }

    # TTS mode
    if text:
        if len(text) > 2500:
            raise ConfigurationError("Text cannot exceed 2500 characters")

        payload["tts_text"] = text

        tts_speed = kwargs.get("tts_speed", 1.0)
        if not (0.8 <= tts_speed <= 2.0):
            raise ConfigurationError("tts_speed must be between 0.8 and 2.0")
        payload["tts_speed"] = tts_speed

        if "tts_voice" in kwargs:
            payload["tts_timbre"] = kwargs["tts_voice"]

    # Custom audio mode
    if audio_url:
        payload["local_dubbing_url"] = audio_url

    if "callback_url" in kwargs:
        payload["callback_url"] = kwargs["callback_url"]

    logger.info(f"Creating lip-sync task for video: {video_id}")

    try:
        task_id = await provider.client.create_task(
            endpoint="/v1/videos/lip-sync",
            payload=payload
        )

        logger.info(f"Lip-sync task created: {task_id}")

        task_result = await provider.client.poll_until_complete(
            endpoint="/v1/videos/lip-sync",
            task_id=task_id,
        )

        videos = task_result.get("videos", [])
        if not videos:
            raise ProviderError("No videos in lip-sync task result")

        video_url = videos[0].get("url")
        if not video_url:
            raise ProviderError("No video URL in lip-sync task result")

        logger.info(f"Lip-sync video generated: {video_url}")

        video_bytes = await provider.client.download_video(video_url)
        logger.info(f"Lip-sync video downloaded: {len(video_bytes)} bytes")

        return video_bytes

    except Exception as e:
        logger.error(f"Lip-sync generation failed: {str(e)}")
        raise
