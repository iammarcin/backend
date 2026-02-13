"""Helpers for Flux image generation provider."""

from __future__ import annotations

import asyncio
import logging
from math import gcd
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from features.chat.utils.websocket_runtime import WorkflowRuntime

import httpx

from core.exceptions import ProviderError
from .flux import (
    download_image,
    find_first_base64,
    find_first_url,
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


async def poll_for_result(
    *,
    task_id: str | None,
    polling_url: str | None,
    cancel_url: str | None = None,
    runtime: "WorkflowRuntime" | None = None,
    api_key: str,
    api_base_url: str,
    api_version: str,
) -> bytes:
    """Poll Flux API until the task completes and return image bytes."""

    if polling_url:
        url = polling_url
        params = {"id": task_id} if task_id else None
    else:
        if not task_id:
            raise ProviderError(
                "Flux polling requires a task ID", provider="flux_image"
            )
        url = f"{api_base_url}/{api_version}/fetch/{task_id}"
        params = None

    headers = {"accept": "application/json", "x-key": api_key}

    logger.info(
        "Starting Flux polling (task_id=%s, has_cancel_url=%s)",
        task_id,
        bool(cancel_url),
    )

    async with httpx.AsyncClient(timeout=30) as client:
        for attempt in range(1, 61):
            if runtime and runtime.is_cancelled():
                logger.info(
                    "Flux image generation cancelled (task_id=%s, attempt=%d)",
                    task_id,
                    attempt,
                )
                if cancel_url:
                    await cancel_fal_job(cancel_url, headers, client)
                raise asyncio.CancelledError("Image generation cancelled by user")

            response = await client.get(url, headers=headers, params=params)
            if response.status_code >= 400:
                logger.error(
                    "Flux fetch error %s: %s", response.status_code, response.text
                )
                raise ProviderError("Flux polling failed", provider="flux_image")

            data = response.json()
            status = (data.get("status") or "").lower()
            if status in _SUCCESS_STATUSES or data.get("result"):
                logger.info("Flux polling completed (task_id=%s)", task_id)
                return await decode_image_from_response(data, api_key)
            if status in _FAILURE_STATUSES:
                raise ProviderError("Flux generation failed", provider="flux_image")

            await asyncio.sleep(1)

    raise ProviderError("Flux generation timed out", provider="flux_image")


async def decode_image_from_response(data: dict[str, Any], api_key: str) -> bytes:
    """Decode base64 image data from a Flux API response."""
    status = (data.get("status") or "").lower()
    if status and status not in _SUCCESS_STATUSES:
        if status in _PENDING_STATUSES:
            raise ProviderError(
                f"Cannot decode image while status={status}", provider="flux_image"
            )
        raise ProviderError(
            f"Flux generation not complete (status={status})", provider="flux_image"
        )

    image_bytes = find_first_base64(data)
    if image_bytes:
        return image_bytes

    image_url = find_first_url(data)
    if image_url:
        return await download_image(image_url, api_key)

    raise ProviderError("Flux API returned no image data", provider="flux_image")


def build_payload(
    prompt: str,
    model_name: str,
    width: int,
    height: int,
    guidance: float | None,
    steps: int | None,
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Build the payload for the Flux API request."""
    payload: dict[str, Any] = {"prompt": prompt}
    payload.update(_dimension_payload(model_name, width, height, kwargs))
    output_format = kwargs.get("output_format")
    payload["output_format"] = str(output_format) if output_format else "png"

    if guidance is not None:
        payload["guidance"] = guidance
    if steps is not None:
        payload["steps"] = steps

    passthrough_fields = {
        "seed",
        "prompt_upsampling",
        "safety_tolerance",
        "image_prompt",
        "input_image",
        "input_image_2",
        "input_image_3",
        "input_image_4",
        "webhook_url",
        "webhook_secret",
    }
    for field in passthrough_fields:
        if field in kwargs and kwargs[field] is not None:
            payload[field] = kwargs[field]

    return payload


def _dimension_payload(
    model_name: str, width: int, height: int, kwargs: dict[str, Any]
) -> dict[str, Any]:
    """Return payload fields for model-specific size requirements."""
    if _requires_aspect_ratio(model_name):
        aspect_ratio = kwargs.get("aspect_ratio") or _aspect_ratio_from_size(width, height)
        return {"aspect_ratio": aspect_ratio}
    return {"width": int(width), "height": int(height)}


def _requires_aspect_ratio(model_name: str) -> bool:
    """Check if the model requires aspect ratio."""
    return "kontext" in model_name


def _aspect_ratio_from_size(width: int, height: int) -> str:
    """Calculate aspect ratio from width and height."""
    width = max(int(width), 1)
    height = max(int(height), 1)
    ratio = gcd(width, height) or 1
    return f"{width // ratio}:{height // ratio}"


async def cancel_fal_job(
    cancel_url: str,
    headers: dict[str, str],
    client: httpx.AsyncClient,
) -> None:
    """Cancel a fal.ai Queue job via cancel endpoint."""
    try:
        logger.info("Calling fal.ai cancel endpoint: %s", cancel_url)
        response = await client.put(cancel_url, headers=headers)
        if response.status_code == 200:
            logger.info("Flux job cancelled successfully via fal.ai API")
        else:
            logger.warning(
                "Flux cancel failed: status=%d, body=%s",
                response.status_code,
                response.text,
            )
    except Exception as exc:
        logger.warning("Failed to cancel Flux job: %s", exc)
