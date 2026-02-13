"""Helpers for image generation within chat workflows."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from core.exceptions import ProviderError
from core.streaming.manager import StreamingManager
from features.image.service import ImageService

logger = logging.getLogger(__name__)


async def generate_image_from_text(
    *,
    text_response: str,
    input_image_url: Optional[str],
    image_mode: Optional[str],
    settings: Dict[str, Any],
    customer_id: int,
    manager: StreamingManager,
    timings: Dict[str, float],
) -> Dict[str, Any]:
    """Trigger image generation using the LLM's response as prompt.

    This helper emits streaming events only; the owning workflow with the
    completion token closes the stream.
    """

    try:
        await manager.send_to_queues(
            {
                "type": "custom_event",
                "event_type": "image",
                "content": {
                    "type": "image",
                    "message": "imageGenerationStarted",
                },
            }
        )

        timings["image_request_sent_time"] = time.time()

        image_service = ImageService()
        image_result = await image_service.generate(
            prompt=text_response,
            settings=settings,
            customer_id=customer_id,
            input_image_url=input_image_url,
        )
        logger.info(
            "Image generation triggered from chat stream (customer=%s, mode=%s)",
            customer_id,
            image_mode,
        )

        timings["image_response_time"] = time.time()
        duration = timings["image_response_time"] - timings["image_request_sent_time"]

        await manager.send_to_queues(
            {
                "type": "custom_event",
                "event_type": "image",
                "content": {
                    "type": "image",
                    "message": "imageGenerated",
                    "image_url": image_result.get("image_url"),
                    "generated_by": image_result.get("model"),
                    "image_generation_settings": image_result.get("settings", {}),
                    "image_generation_request": {
                        "prompt": text_response,
                        "input_image_url": input_image_url,
                        "image_mode": image_mode,
                    },
                    "duration": duration,
                },
            }
        )

        return image_result
    except ProviderError as exc:
        logger.error("Image provider error: %s", exc)
        await manager.send_to_queues(
            {
                "type": "error",
                "content": f"Image generation failed: {exc}",
                "stage": "image",
            }
        )
        return {"error": str(exc)}
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Unexpected error generating image: %s", exc, exc_info=True)
        await manager.send_to_queues(
            {
                "type": "error",
                "content": f"Image generation failed: {exc}",
                "stage": "image",
            }
        )
        return {"error": str(exc)}


__all__ = ["generate_image_from_text"]
