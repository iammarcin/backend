"""Business logic for video generation."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from features.chat.workflow_runtime import WorkflowRuntime

from infrastructure.aws.storage import StorageService
from .generation import generate_video as generate_video_flow
from .generation import extend_video as extend_video_flow

logger = logging.getLogger(__name__)


class VideoService:
    """Coordinate video generation providers and storage."""

    def __init__(self, storage_service: StorageService | None = None) -> None:
        self.storage_service = storage_service or StorageService()

    async def generate(
        self,
        *,
        prompt: str,
        settings: Dict[str, Any],
        customer_id: int,
        input_image_url: str | None = None,
        save_to_s3: bool = True,
        runtime: "WorkflowRuntime" | None = None,
    ) -> Dict[str, Any]:
        """Generate a video and optionally persist it to S3."""
        return await generate_video_flow(
            prompt=prompt,
            settings=settings,
            customer_id=customer_id,
            storage_service=self.storage_service,
            input_image_url=input_image_url,
            save_to_s3=save_to_s3,
            runtime=runtime,
        )

    async def extend_video(
        self,
        *,
        video_id: str,
        prompt: str | None = None,
        settings: Dict[str, Any] | None = None,
        customer_id: int = 0,
        save_to_s3: bool = True,
    ) -> Dict[str, Any]:
        """Extend existing video."""
        return await extend_video_flow(
            video_id=video_id,
            storage_service=self.storage_service,
            prompt=prompt,
            settings=settings,
            customer_id=customer_id,
            save_to_s3=save_to_s3,
        )


class VideoGenerationService:
    """High-level wrapper that adapts VideoService responses for tools."""

    def __init__(self, video_service: VideoService | None = None) -> None:
        self._video_service = video_service or VideoService()

    async def generate_video(
        self,
        *,
        prompt: str,
        customer_id: int,
        settings: Dict[str, Any],
        mode: str = "text-to-video",
        save_to_db: bool = True,
        runtime: "WorkflowRuntime" | None = None,
    ) -> Dict[str, Any]:
        """Generate a video and normalize the response for agentic tools."""
        input_image_url: str | None = None
        if mode == "image-to-video":
            video_settings = settings.get("video", {}) if isinstance(settings, dict) else {}
            input_image_url = video_settings.get("input_image_url")

        result = await self._video_service.generate(
            prompt=prompt,
            settings=settings,
            customer_id=customer_id,
            input_image_url=input_image_url,
            save_to_s3=save_to_db,
            runtime=runtime,
        )

        metadata = result.get("settings", {})

        return {
            "video_url": result.get("video_url"),
            "video_id": result.get("video_id"),
            "model": metadata.get("model", result.get("model")),
            "provider": metadata.get("provider"),
            "duration": metadata.get("duration_seconds", result.get("duration")),
            "settings": metadata,
        }

    async def extend_video(
        self,
        *,
        video_id: str,
        prompt: str | None = None,
        settings: Dict[str, Any] | None = None,
        customer_id: int = 0,
        save_to_s3: bool = True,
    ) -> Dict[str, Any]:
        """Extend existing video."""
        return await self._video_service.extend_video(
            video_id=video_id,
            prompt=prompt,
            settings=settings,
            customer_id=customer_id,
            save_to_s3=save_to_s3,
        )
