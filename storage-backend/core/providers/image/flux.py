"""Flux image generation provider."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from features.chat.utils.websocket_runtime import WorkflowRuntime

import httpx

from core.utils.env import get_env
from core.exceptions import ProviderError
from core.providers.capabilities import ProviderCapabilities
from core.providers.base import BaseImageProvider
from .utils.flux_helpers import (
    build_payload,
    poll_for_result,
    decode_image_from_response,
)

logger = logging.getLogger(__name__)

_SUCCESS_STATUSES = {"completed", "success", "succeeded", "ready"}
_PENDING_STATUSES = {
    "pending",
    "queued",
    "processing",
    "running",
    "starting",
    "submitted",
}
_FAILURE_STATUSES = {"failed", "error", "cancelled"}


class FluxImageProvider(BaseImageProvider):
    """Generate images using the Flux (Black Forest Labs) API."""

    def __init__(self) -> None:
        api_key = get_env("FLUX_API_KEY")
        if not api_key:
            raise ProviderError("Flux API key not configured", provider="flux_image")

        self.capabilities = ProviderCapabilities()
        self.api_key = api_key
        self.api_version = str(get_env("FLUX_API_VERSION", default="v1") or "v1")
        base_url = str(
            get_env("FLUX_API_BASE_URL", default="https://api.eu.bfl.ai")
            or "https://api.eu.bfl.ai"
        )
        self.api_base_url = base_url.rstrip("/")
        self.provider_name = "flux"
        self.last_quality = "medium"

    async def generate(
        self,
        prompt: str,
        model: str | None = "flux-dev",
        width: int = 1024,
        height: int = 1024,
        guidance: float | None = None,
        steps: int | None = None,
        runtime: "WorkflowRuntime" | None = None,
        **kwargs: Any,
    ) -> bytes:
        """Generate an image for the supplied prompt."""
        if not prompt:
            raise ProviderError("Prompt cannot be empty", provider="flux_image")

        model_name = (model or "flux-dev").strip().lower().replace(" ", "-")
        url = f"{self.api_base_url}/{self.api_version}/{model_name}"

        self.last_quality = str(kwargs.get("quality", "medium"))

        payload = build_payload(
            prompt, model_name, width, height, guidance, steps, kwargs
        )

        headers = {
            "accept": "application/json",
            "x-key": self.api_key,
            "content-type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, json=payload, headers=headers)

        if response.status_code >= 400:
            logger.error("Flux API error %s: %s", response.status_code, response.text)
            raise ProviderError(
                f"Flux API error {response.status_code}",
                provider="flux_image",
            )

        data = response.json()
        status = (data.get("status") or "").lower()
        task_id = data.get("id") or data.get("task_id")
        polling_url = data.get("polling_url")
        logger.info(
            "Flux API initial response",
            extra={
                "status": status or None,
                "model": model_name,
                "has_task_id": bool(task_id),
                "has_polling_url": bool(polling_url),
            },
        )

        if status in _SUCCESS_STATUSES or data.get("result"):
            return await decode_image_from_response(data, self.api_key)

        if status in _FAILURE_STATUSES:
            raise ProviderError("Flux generation failed", provider="flux_image")

        if polling_url or status in _PENDING_STATUSES or task_id:
            if not (polling_url or task_id):
                raise ProviderError(
                    "Flux API did not return polling information", provider="flux_image"
                )
            return await poll_for_result(
                task_id=task_id,
                polling_url=polling_url,
                cancel_url=kwargs.get("cancel_url"),
                runtime=runtime,
                api_key=self.api_key,
                api_base_url=self.api_base_url,
                api_version=self.api_version,
            )

        raise ProviderError("Flux API returned no image data", provider="flux_image")
