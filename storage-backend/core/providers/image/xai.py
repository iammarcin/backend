"""xAI Grok image generation provider."""

from __future__ import annotations

import base64
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from features.chat.utils.websocket_runtime import WorkflowRuntime

import httpx

from core.utils.env import get_env
from core.exceptions import ProviderError
from core.providers.capabilities import ProviderCapabilities
from core.providers.base import BaseImageProvider

logger = logging.getLogger(__name__)


class XaiImageProvider(BaseImageProvider):
    """Generate images using the xAI Grok image API."""

    def __init__(self) -> None:
        api_key = get_env("XAI_API_KEY")
        if not api_key:
            raise ProviderError("xAI API key not configured", provider="xai_image")

        base_url = get_env("XAI_API_BASE_URL", default="https://api.x.ai/v1") or "https://api.x.ai/v1"
        self.api_key = api_key
        self.base_url = str(base_url).rstrip("/")
        self.capabilities = ProviderCapabilities()
        self.provider_name = "xai"
        self.last_quality = "default"

    async def generate(
        self,
        prompt: str,
        model: str | None = "grok-2-image",
        width: int = 1024,
        height: int = 1024,
        response_format: str = "b64_json",
        runtime: Optional[WorkflowRuntime] = None,
        **kwargs: Any,
    ) -> bytes:
        """Generate an image for the supplied prompt."""

        if not prompt:
            raise ProviderError("Prompt cannot be empty", provider="xai_image")

        # Check cancellation before starting
        if runtime and runtime.is_cancelled():
            raise asyncio.CancelledError("Image generation cancelled before start")

        requested_quality = kwargs.pop("quality", None)
        if requested_quality is not None:
            logger.debug("Ignoring unsupported xAI quality parameter: %s", requested_quality)
        self.last_quality = requested_quality or "default"

        parsed_width, parsed_height = self._resolve_dimensions(width, height, kwargs.get("size"))

        payload: dict[str, Any] = {
            "model": model or "grok-2-image",
            "prompt": prompt,
            "n": kwargs.get("number_of_images", 1),
            "response_format": response_format or "b64_json",
            "width": parsed_width,
            "height": parsed_height,
        }

        optional_fields = {
            "background",
            "moderation",
            "output_format",
            "output_compression",
            "style",
            "user",
            "seed",
        }
        for field in optional_fields:
            if field in kwargs and kwargs[field] is not None:
                payload[field] = kwargs[field]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        url = f"{self.base_url}/images/generations"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, json=payload, headers=headers)

        if response.status_code >= 400:
            try:
                error_payload = response.json()
            except Exception:  # pragma: no cover - defensive JSON parsing
                error_payload = response.text
            logger.error("xAI image generation error: %s - %s", response.status_code, error_payload)
            raise ProviderError(
                f"xAI image error: {error_payload}",
                provider="xai_image",
            )

        data = response.json()
        items = data.get("data") if isinstance(data, dict) else None
        if not items:
            raise ProviderError("xAI returned no image data", provider="xai_image")

        item = items[0]
        if (response_format or "b64_json") == "url":
            image_url = item.get("url") if isinstance(item, dict) else getattr(item, "url", None)
            if not image_url:
                raise ProviderError("xAI response missing URL", provider="xai_image")
            return await self._download_image(image_url)

        image_b64 = None
        if isinstance(item, dict):
            image_b64 = item.get("b64_json") or item.get("image_base64")
        else:
            image_b64 = getattr(item, "b64_json", None)

        if not image_b64:
            raise ProviderError("xAI response missing base64 data", provider="xai_image")

        return base64.b64decode(image_b64)

    async def _download_image(self, url: str) -> bytes:
        """Download an image from a URL using httpx."""

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url)
        if response.status_code >= 400:
            raise ProviderError(f"Failed to download image: {url}", provider="xai_image")
        return response.content

    def _resolve_dimensions(
        self,
        width: int,
        height: int,
        size_override: str | None,
    ) -> tuple[int, int]:
        """Return integer width/height, parsing optional size override."""

        try:
            parsed_width = int(width)
            parsed_height = int(height)
        except (TypeError, ValueError):  # pragma: no cover - defensive guard
            raise ProviderError("Width and height must be integers", provider="xai_image")

        if size_override and isinstance(size_override, str):
            parts = size_override.lower().replace(" ", "").split("x", maxsplit=1)
            if len(parts) == 2:
                try:
                    parsed_width = int(parts[0])
                    parsed_height = int(parts[1])
                except ValueError:
                    logger.warning("Invalid size override provided to xAI image provider: %s", size_override)

        return parsed_width, parsed_height
