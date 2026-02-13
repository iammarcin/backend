"""Business logic for image generation."""

from __future__ import annotations

import base64
import logging
from typing import TYPE_CHECKING, Dict, Optional, Tuple

if TYPE_CHECKING:
    from features.chat.workflow_runtime import WorkflowRuntime

from config.image.aliases import resolve_image_model_alias
from core.exceptions import ProviderError, ValidationError
from core.providers.factory import get_image_provider
from infrastructure.aws.storage import StorageService

logger = logging.getLogger(__name__)


class ImageService:
    """Coordinate image generation providers and storage."""

    async def generate_image(
        self,
        *,
        prompt: str,
        settings: Dict[str, object],
        customer_id: int,
        save_to_s3: bool = True,
        runtime: Optional["WorkflowRuntime"] = None,
        input_image_url: Optional[str] = None,
    ) -> Tuple[Optional[str], bytes, Dict[str, object]]:
        """Generate an image and optionally persist it to S3.

        Args:
            prompt: Text description for image generation
            settings: Provider and generation settings
            customer_id: Customer identifier
            save_to_s3: Whether to upload result to S3
            runtime: Optional workflow runtime for cancellation
            input_image_url: Optional input image URL for image-to-image generation
                             (supported by Flux models)
        """

        if not prompt or not prompt.strip():
            raise ValidationError("Prompt cannot be empty", field="prompt")
        if customer_id <= 0:
            raise ValidationError("Invalid customer_id", field="customer_id")

        settings = settings or {}
        if not isinstance(settings, dict):
            settings = {}

        image_settings = settings.get("image", {}) if isinstance(settings, dict) else {}
        if not isinstance(image_settings, dict):
            image_settings = {}

        model = resolve_image_model_alias(str(image_settings.get("model", "openai")))
        provider = get_image_provider(settings)
        width = int(image_settings.get("width", 1024))
        height = int(image_settings.get("height", 1024))
        quality = str(image_settings.get("quality", "medium"))

        if width <= 0 or height <= 0:
            raise ValidationError("Image dimensions must be positive", field="image.size")

        # Build kwargs for provider-specific features (e.g., input image)
        provider_kwargs: Dict[str, object] = {}
        if input_image_url:
            # Flux supports input_image parameter for image-to-image
            provider_kwargs["input_image"] = input_image_url
            logger.info(
                "Generating image with input image for customer %s with model %s (%sx%s)",
                customer_id,
                model,
                width,
                height,
            )
        else:
            logger.info(
                "Generating image for customer %s with model %s (%sx%s)",
                customer_id,
                model,
                width,
                height,
            )

        try:
            image_bytes = await provider.generate(
                prompt=prompt,
                model=model,
                width=width,
                height=height,
                quality=quality,
                runtime=runtime,
                **provider_kwargs,
            )
        except ProviderError:
            raise
        except ValidationError:
            raise
        except Exception as exc:  # pragma: no cover - unexpected provider failure
            logger.error("Unexpected image provider failure: %s", exc)
            raise ProviderError(f"Failed to generate image: {exc}") from exc

        s3_url: Optional[str] = None
        if save_to_s3:
            storage = StorageService()
            s3_url = await storage.upload_image(
                image_bytes=image_bytes,
                customer_id=customer_id,
                file_extension="png",
            )
            logger.info("Image uploaded to S3 for customer %s", customer_id)
        else:
            logger.info(
                "Skipping S3 upload for customer %s (save_to_s3=%s)",
                customer_id,
                save_to_s3,
            )

        metadata: Dict[str, object] = {
            "provider": getattr(provider, "provider_name", "openai"),
            "model": model,
            "width": width,
            "height": height,
            "quality": getattr(provider, "last_quality", quality),
        }

        return s3_url, image_bytes, metadata

    async def generate(
        self,
        *,
        prompt: str,
        settings: Dict[str, object],
        customer_id: int,
        input_image_url: Optional[str] = None,
    ) -> Dict[str, object]:
        """Generate an image and return metadata suitable for streaming workflows."""

        s3_url, _image_bytes, metadata = await self.generate_image(
            prompt=prompt,
            settings=settings,
            customer_id=customer_id,
            save_to_s3=True,
        )

        response: Dict[str, object] = {
            "image_url": s3_url,
            "model": metadata.get("model"),
            "settings": {
                "width": metadata.get("width"),
                "height": metadata.get("height"),
                "quality": metadata.get("quality"),
                "prompt": prompt,
            },
        }

        if input_image_url:
            response["input_image_url"] = input_image_url

        return response


class ImageGenerationService:
    """High-level service wrapper for agentic workflows."""

    def __init__(self, image_service: ImageService | None = None) -> None:
        self._image_service = image_service or ImageService()

    async def generate_image(
        self,
        *,
        prompt: str,
        customer_id: int,
        settings: Dict[str, object],
        save_to_db: bool = True,
        runtime: Optional["WorkflowRuntime"] = None,
    ) -> Dict[str, object]:
        """Generate an image and return metadata consumed by tools."""

        s3_url, image_bytes, metadata = await self._image_service.generate_image(
            prompt=prompt,
            settings=settings,
            customer_id=customer_id,
            save_to_s3=save_to_db,
            runtime=runtime,
        )

        image_url = s3_url
        if not image_url and image_bytes:
            image_url = "data:image/png;base64," + base64.b64encode(image_bytes).decode("utf-8")

        return {
            "image_url": image_url,
            "image_id": metadata.get("image_id"),
            "provider": metadata.get("provider"),
            "model": metadata.get("model"),
            "settings": metadata,
        }
