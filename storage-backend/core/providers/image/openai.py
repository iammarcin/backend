"""OpenAI image generation provider implementation."""

from __future__ import annotations

import asyncio
import base64
import io
import logging
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from features.chat.utils.websocket_runtime import WorkflowRuntime

import httpx

from core.clients.ai import ai_clients
from core.exceptions import ProviderError
from core.providers.capabilities import ProviderCapabilities
from core.providers.base import BaseImageProvider

logger = logging.getLogger(__name__)


class OpenAIImageProvider(BaseImageProvider):
    """Image generation provider backed by OpenAI's Images API."""

    def __init__(self) -> None:
        self.client = ai_clients.get("openai")
        if not self.client:
            raise ProviderError("OpenAI client not initialized", provider="openai_image")

        self.capabilities = ProviderCapabilities(streaming=False, reasoning=False)
        self.provider_name = "openai"
        self.last_quality = "medium"

    async def generate(
        self,
        prompt: str,
        model: str | None = "gpt-image-1",
        width: int = 1024,
        height: int = 1024,
        quality: str = "medium",
        runtime: Optional["WorkflowRuntime"] = None,
        input_image: Optional[str] = None,
        **kwargs: Any,
    ) -> bytes:
        """Generate an image for the supplied prompt.

        Args:
            prompt: Text description for image generation or editing
            model: Model name to use
            width: Image width
            height: Image height
            quality: Quality level (low/medium/high)
            runtime: Optional workflow runtime for cancellation
            input_image: Optional URL of input image for image editing
        """

        if not prompt or not prompt.strip():
            raise ProviderError("Prompt cannot be empty", provider="openai_image")

        size = f"{int(width)}x{int(height)}"
        model_name = model or "gpt-image-1"

        allowed_qualities = {"low", "medium", "high", "auto"}
        normalized_quality = (quality or "medium").lower()
        if normalized_quality == "standard":
            normalized_quality = "medium"
        elif normalized_quality not in allowed_qualities:
            logger.warning("Unsupported OpenAI image quality '%s'; falling back to 'medium'", quality)
            normalized_quality = "medium"

        quality = normalized_quality
        self.last_quality = quality

        # If input image is provided, use the edit endpoint
        if input_image:
            return await self._edit_image(
                prompt=prompt,
                model_name=model_name,
                size=size,
                quality=quality,
                input_image_url=input_image,
            )

        effective_prompt = prompt
        if kwargs.get("disable_safe_prompt_adjust", True):
            effective_prompt = (
                "I NEED to test how the tool works with extremely simple prompts. "
                "DO NOT add any detail, just use it AS-IS: "
                f"{prompt}"
            )

        # Use Images API for all models (gpt-image-*, dall-e-*)
        logger.info(
            "Generating image with OpenAI: model=%s size=%s quality=%s",
            model_name,
            size,
            quality,
        )

        # Build kwargs - gpt-image models don't support response_format
        generate_kwargs: dict[str, Any] = {
            "prompt": effective_prompt,
            "model": model_name,
            "size": size,
            "n": 1,
        }

        # Only add quality for gpt-image models (not dall-e-2)
        if model_name.startswith("gpt-image"):
            generate_kwargs["quality"] = quality

        # Only add response_format for dall-e models
        if model_name.startswith("dall-e"):
            generate_kwargs["response_format"] = "b64_json"
            generate_kwargs["quality"] = quality

        try:
            response = await asyncio.to_thread(
                self.client.images.generate,
                **generate_kwargs,
            )
        except Exception as exc:
            logger.error("OpenAI image generation error: %s", exc)
            raise ProviderError(f"OpenAI image error: {exc}", provider="openai_image") from exc

        # Extract image - try b64_json first, then URL
        try:
            result = response.data[0]
            if hasattr(result, "b64_json") and result.b64_json:
                image_bytes = base64.b64decode(result.b64_json)
            elif hasattr(result, "url") and result.url:
                async with httpx.AsyncClient(timeout=60) as client:
                    download_resp = await client.get(result.url)
                    image_bytes = download_resp.content
            else:
                raise ProviderError(
                    "OpenAI response missing image data", provider="openai_image"
                )
        except (AttributeError, IndexError) as exc:
            logger.error("Unexpected OpenAI image response structure: %s", exc)
            raise ProviderError("Invalid response from OpenAI image API", provider="openai_image") from exc

        logger.info("OpenAI image generated successfully (%s bytes)", len(image_bytes))

        return image_bytes

    async def _edit_image(
        self,
        *,
        prompt: str,
        model_name: str,
        size: str,
        quality: str,
        input_image_url: str,
    ) -> bytes:
        """Edit an image using OpenAI's images.edit endpoint."""

        logger.info(
            "Editing image with OpenAI: model=%s size=%s quality=%s",
            model_name,
            size,
            quality,
        )

        # Download the input image
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(input_image_url)
                response.raise_for_status()
            input_image_bytes = response.content
            logger.debug("Downloaded input image: %d bytes", len(input_image_bytes))
        except httpx.HTTPError as exc:
            logger.error("Failed to download input image: %s", exc)
            raise ProviderError(
                f"Failed to download input image: {exc}", provider="openai_image"
            ) from exc

        # Create a file-like object for the API
        image_file = io.BytesIO(input_image_bytes)
        image_file.name = "input.png"

        try:
            response = await asyncio.to_thread(
                self.client.images.edit,
                image=image_file,
                prompt=prompt,
                model=model_name,
                size=size,
                n=1,
            )
        except Exception as exc:
            logger.error("OpenAI image edit error: %s", exc)
            raise ProviderError(f"OpenAI image edit error: {exc}", provider="openai_image") from exc

        # Extract the result
        try:
            result = response.data[0]
            if hasattr(result, "b64_json") and result.b64_json:
                image_bytes = base64.b64decode(result.b64_json)
            elif hasattr(result, "url") and result.url:
                async with httpx.AsyncClient(timeout=30) as client:
                    download_resp = await client.get(result.url)
                    image_bytes = download_resp.content
            else:
                raise ProviderError(
                    "OpenAI edit response missing image data", provider="openai_image"
                )
        except (AttributeError, IndexError) as exc:
            logger.error("Unexpected OpenAI edit response structure: %s", exc)
            raise ProviderError(
                "Invalid response from OpenAI image edit API", provider="openai_image"
            ) from exc

        logger.info("OpenAI image edited successfully (%s bytes)", len(image_bytes))
        return image_bytes
