"""KlingAI video generation provider."""

import logging
from typing import Optional, List

from config.video.providers import klingai as klingai_config
from core.exceptions import ConfigurationError
from core.providers.capabilities import ProviderCapabilities
from core.providers.base import BaseVideoProvider
from core.providers.video.utils.klingai import (
    KlingAIAuth,
    KlingAIClient,
    KlingAIModel,
    VideoMode,
    AspectRatio,
    generators_text,
    generators_image,
    generators_multi,
    generators_extend,
    generators_avatar,
)

logger = logging.getLogger(__name__)


class KlingAIVideoProvider(BaseVideoProvider):
    """KlingAI video generation with text/image-to-video, extensions, and avatars."""

    provider_name = "klingai"
    default_model = klingai_config.DEFAULT_MODEL

    allowed_models = [model.value for model in KlingAIModel]
    allowed_durations = [5, 10]
    allowed_aspect_ratios = [ratio.value for ratio in AspectRatio]
    allowed_modes = [mode.value for mode in VideoMode]

    def __init__(self):
        super().__init__()

        if not klingai_config.ACCESS_KEY:
            raise ConfigurationError("KLINGAI_ACCESS_KEY not configured")
        if not klingai_config.SECRET_KEY:
            raise ConfigurationError("KLINGAI_SECRET_KEY not configured")

        self.auth = KlingAIAuth(
            access_key=klingai_config.ACCESS_KEY,
            secret_key=klingai_config.SECRET_KEY,
        )
        self.client = KlingAIClient(
            auth=self.auth,
            base_url=klingai_config.API_BASE_URL,
            timeout=klingai_config.TIMEOUT,
            poll_interval=klingai_config.POLL_INTERVAL,
        )
        self.capabilities = ProviderCapabilities(
            streaming=False,
            image_to_video=True,
        )
        logger.info("KlingAI video provider initialized")

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        runtime: Optional["WorkflowRuntime"] = None,
        **kwargs
    ) -> bytes:
        """Generate video from text prompt. Returns video bytes."""
        return await generators_text.generate_text_to_video(
            self, prompt, model, runtime, **kwargs
        )

    async def generate_from_image(
        self,
        prompt: str,
        image_url: str,
        model: Optional[str] = None,
        runtime: Optional["WorkflowRuntime"] = None,
        **kwargs
    ) -> bytes:
        """Generate video from image with optional text guidance. Returns video bytes."""
        return await generators_image.generate_image_to_video(
            self, prompt, image_url, model, runtime, **kwargs
        )

    async def generate_from_multiple_images(
        self,
        prompt: str,
        image_urls: List[str],
        model: Optional[str] = None,
        **kwargs
    ) -> bytes:
        """Generate video from 2-4 images. Prompt required. Returns video bytes."""
        return await generators_multi.generate_multi_image_to_video(
            self, prompt, image_urls, model, **kwargs
        )

    async def extend_video(
        self,
        video_id: str,
        prompt: Optional[str] = None,
        **kwargs
    ) -> bytes:
        """Extend existing video by 4-5 seconds (max 180s total). Returns video bytes."""
        return await generators_extend.extend_video(self, video_id, prompt, **kwargs)

    async def generate_avatar(
        self,
        image_url: str,
        text: Optional[str] = None,
        audio_url: Optional[str] = None,
        model: str = "avatar-standard",
        **kwargs
    ) -> bytes:
        """Generate talking head video from face image with TTS or lip-sync."""
        return await generators_avatar.generate_avatar_video(
            self, image_url, text, audio_url, model, **kwargs
        )

    async def add_lip_sync(
        self,
        video_id: str,
        text: Optional[str] = None,
        audio_url: Optional[str] = None,
        **kwargs
    ) -> bytes:
        """Add lip-sync to existing video using TTS text or custom audio."""
        return await generators_avatar.generate_lip_sync(
            self, video_id, text, audio_url, **kwargs
        )
