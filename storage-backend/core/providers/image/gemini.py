"""Google Gemini image generation provider."""

from __future__ import annotations

import asyncio
import base64
import logging
import math
from typing import TYPE_CHECKING, Any, Iterable, Optional, Sequence

if TYPE_CHECKING:
    from features.chat.utils.websocket_runtime import WorkflowRuntime

import httpx
from google.genai import types  # type: ignore

from core.clients.ai import ai_clients
from core.exceptions import ProviderError
from core.providers.base import BaseImageProvider
from core.providers.capabilities import ProviderCapabilities

logger = logging.getLogger(__name__)


class GeminiImageProvider(BaseImageProvider):
    """Generate images using Google Gemini Imagen and Flash models."""

    def __init__(self) -> None:
        self.client = ai_clients.get("gemini")
        if not self.client:
            raise ProviderError("Gemini client not initialized", provider="gemini_image")

        self.capabilities = ProviderCapabilities()
        self.provider_name = "gemini"

    async def generate(
        self,
        *,
        prompt: str,
        model: str | None = "imagen-4.0-generate-001",
        width: int = 1024,
        height: int = 1024,
        number_of_images: int = 1,
        runtime: Optional["WorkflowRuntime"] = None,
        input_image: Optional[str] = None,
        **_: Any,
    ) -> bytes:
        """Generate an image for the supplied prompt.

        Args:
            prompt: Text description for image generation
            model: Model name to use
            width: Image width
            height: Image height
            number_of_images: Number of images to generate
            runtime: Optional workflow runtime for cancellation
            input_image: Optional URL of input image for image-to-image generation
        """

        if not prompt:
            raise ProviderError("Prompt cannot be empty", provider="gemini_image")

        # Check cancellation before starting
        if runtime and runtime.is_cancelled():
            raise asyncio.CancelledError("Image generation cancelled before start")

        model_name = (model or "imagen-4.0-generate-001").strip()
        aspect_ratio = self._aspect_ratio_string(width, height)

        if self._is_imagen_model(model_name):
            if input_image:
                logger.warning(
                    "Imagen models do not support input images; ignoring input_image"
                )
            return await self._generate_with_imagen_model(
                prompt=prompt,
                model_name=model_name,
                aspect_ratio=aspect_ratio,
                number_of_images=number_of_images,
            )

        return await self._generate_with_flash_model(
            prompt=prompt,
            model_name=model_name,
            aspect_ratio=aspect_ratio,
            input_image_url=input_image,
        )

    async def _generate_with_imagen_model(
        self,
        *,
        prompt: str,
        model_name: str,
        aspect_ratio: str,
        number_of_images: int,
    ) -> bytes:
        """Call Imagen specific API for legacy Gemini models."""

        config = types.GenerateImagesConfig(
            number_of_images=number_of_images,
            aspect_ratio=aspect_ratio,
        )

        logger.info(
            "Generating Gemini Imagen image with model=%s aspect_ratio=%s",
            model_name,
            aspect_ratio,
        )

        try:
            response = await asyncio.to_thread(
                self.client.models.generate_images,
                model=model_name,
                prompt=prompt,
                config=config,
            )
        except Exception as exc:  # pragma: no cover
            logger.error("Gemini Imagen generation error: %s", exc)
            raise ProviderError(f"Gemini image error: {exc}", provider="gemini_image") from exc

        if not getattr(response, "images", None):
            raise ProviderError("Gemini returned no images", provider="gemini_image")

        image = response.images[0]
        image_bytes = None
        if hasattr(image, "image_bytes") and image.image_bytes:
            image_bytes = image.image_bytes
        elif hasattr(image, "data") and image.data:
            image_bytes = image.data
        elif hasattr(image, "b64_json"):
            image_bytes = base64.b64decode(image.b64_json)

        if image_bytes is None:
            raise ProviderError("Gemini image response missing data", provider="gemini_image")

        return bytes(image_bytes)

    async def _generate_with_flash_model(
        self,
        *,
        prompt: str,
        model_name: str,
        aspect_ratio: str,
        input_image_url: Optional[str] = None,
    ) -> bytes:
        """Call the generative endpoint for Gemini Flash image models."""

        # Build contents list - prompt and optional input image
        contents: list[Any] = []

        if input_image_url:
            logger.info(
                "Generating Gemini Flash image with input image: model=%s aspect_ratio=%s",
                model_name,
                aspect_ratio,
            )
            # Download and add the input image
            image_part = await self._download_image_as_part(input_image_url)
            contents.append(image_part)
        else:
            logger.info(
                "Generating Gemini Flash image with model=%s aspect_ratio=%s",
                model_name,
                aspect_ratio,
            )

        contents.append(prompt)

        image_config = types.ImageConfig(aspect_ratio=aspect_ratio)
        config = types.GenerateContentConfig(image_config=image_config)

        try:
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=model_name,
                contents=contents,
                config=config,
            )
        except Exception as exc:  # pragma: no cover
            logger.error("Gemini Flash image generation error: %s", exc)
            raise ProviderError(f"Gemini image error: {exc}", provider="gemini_image") from exc

        image_bytes = self._extract_flash_image_bytes(response)
        if image_bytes is None:
            # Log what Gemini actually returned for debugging
            text_content = self._extract_text_from_response(response)
            if text_content:
                logger.warning(
                    "Gemini returned text instead of image: %s",
                    text_content[:500],
                )
                raise ProviderError(
                    f"Gemini returned text instead of image: {text_content[:200]}",
                    provider="gemini_image",
                )
            raise ProviderError(
                "Gemini flash image response missing data", provider="gemini_image"
            )

        return image_bytes

    async def _download_image_as_part(self, image_url: str) -> types.Part:
        """Download an image from URL and return as a Gemini Part."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(image_url)
                response.raise_for_status()

            image_bytes = response.content
            content_type = response.headers.get("content-type", "image/png")

            # Normalize mime type
            if "jpeg" in content_type or "jpg" in content_type:
                mime_type = "image/jpeg"
            elif "webp" in content_type:
                mime_type = "image/webp"
            elif "gif" in content_type:
                mime_type = "image/gif"
            else:
                mime_type = "image/png"

            logger.debug(
                "Downloaded input image: %d bytes, mime_type=%s",
                len(image_bytes),
                mime_type,
            )

            return types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

        except httpx.HTTPError as exc:
            logger.error("Failed to download input image from %s: %s", image_url, exc)
            raise ProviderError(
                f"Failed to download input image: {exc}", provider="gemini_image"
            ) from exc

    def _extract_flash_image_bytes(self, response: Any) -> bytes | None:
        """Extract inline image data from a generate_content response."""

        for part in self._iter_response_parts(response):
            inline_data = getattr(part, "inline_data", None)
            if inline_data and getattr(inline_data, "data", None):
                data = inline_data.data
                if isinstance(data, bytes):
                    return data
                return base64.b64decode(data)

        return None

    def _extract_text_from_response(self, response: Any) -> str | None:
        """Extract any text content from a Gemini response for error reporting."""
        text_parts = []
        for part in self._iter_response_parts(response):
            if hasattr(part, "text") and part.text:
                text_parts.append(part.text)
        return " ".join(text_parts) if text_parts else None

    @staticmethod
    def _iter_response_parts(response: Any) -> Iterable[Any]:
        """Yield content parts from a Gemini generate_content response."""

        parts: Sequence[Any] | None = getattr(response, "parts", None)
        if parts:
            yield from parts
            return

        candidates = getattr(response, "candidates", None)
        if not candidates:
            return

        for candidate in candidates:
            content = getattr(candidate, "content", None)
            candidate_parts: Sequence[Any] | None = getattr(content, "parts", None)
            if candidate_parts:
                yield from candidate_parts

    @staticmethod
    def _is_imagen_model(model_name: str) -> bool:
        return model_name.lower().startswith("imagen-")

    @staticmethod
    def _aspect_ratio_string(width: int, height: int) -> str:
        """Return a simplified aspect ratio string (e.g., 16:9)."""

        if width <= 0 or height <= 0:
            return "1:1"
        gcd = math.gcd(int(width), int(height))
        return f"{int(width // gcd)}:{int(height // gcd)}"


__all__ = ["GeminiImageProvider"]
