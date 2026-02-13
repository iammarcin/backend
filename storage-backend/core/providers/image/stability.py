"""Stability AI image generation provider."""

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


class StabilityImageProvider(BaseImageProvider):
    """Generate images using the Stability AI API."""

    def __init__(self) -> None:
        api_key = get_env("STABILITY_API_KEY")
        if not api_key:
            raise ProviderError("Stability API key not configured", provider="stability_image")

        self.api_key = api_key
        self.capabilities = ProviderCapabilities()
        self.provider_name = "stability"

    async def _request_image(self, url: str, payload: dict[str, Any], headers: dict[str, str]) -> bytes:
        files = {key: (None, str(value)) for key, value in payload.items()}

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, files=files, headers=headers)

        if response.status_code >= 400:
            logger.error("Stability API error %s: %s", response.status_code, response.text)
            raise ProviderError(
                f"Stability API error {response.status_code}",
                provider="stability_image",
            )

        if response.headers.get("content-type", "").startswith("image"):
            return response.content

        data = response.json()
        artifacts = data.get("artifacts", [])
        if not artifacts:
            raise ProviderError("Stability API returned no artifacts", provider="stability_image")

        image_b64 = artifacts[0].get("base64") or artifacts[0].get("b64_json")
        if not image_b64:
            raise ProviderError("Stability API returned no image data", provider="stability_image")

        return base64.b64decode(image_b64)

    async def generate(
        self,
        prompt: str,
        model: str | None = "core",
        width: int = 1024,
        height: int = 1024,
        runtime: Optional[WorkflowRuntime] = None,
        **kwargs: Any,
    ) -> bytes:
        """Generate an image for the supplied prompt."""

        if not prompt:
            raise ProviderError("Prompt cannot be empty", provider="stability_image")

        # Check cancellation before starting
        if runtime and runtime.is_cancelled():
            raise asyncio.CancelledError("Image generation cancelled before start")

        model_name = (model or "core").lower()
        if model_name.startswith("sd3.5"):
            endpoint_model = "sd3"
        else:
            endpoint_model = model_name

        url = f"https://api.stability.ai/v2beta/stable-image/generate/{endpoint_model}"
        headers = {
            "authorization": f"Bearer {self.api_key}",
            "accept": "image/*, application/json",
        }

        payload: dict[str, Any] = {
            "prompt": prompt,
            "output_format": "png",
            "width": int(width),
            "height": int(height),
        }

        optional_fields = {"negative_prompt", "seed", "cfg_scale", "style_preset", "mode"}
        for field in optional_fields:
            if field in kwargs:
                payload[field] = kwargs[field]

        logger.info("Generating Stability image with model=%s", model_name)
        return await self._request_image(url, payload, headers)
