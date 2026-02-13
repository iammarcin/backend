"""Clarification workflow executor for WebSocket dispatcher.

Handles the clarification workflow where users respond to clarifying questions
to refine their original request.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from core.streaming.manager import StreamingManager
from features.chat.service import ChatService
from features.chat.utils.clarification_workflow import handle_clarification_workflow


logger = logging.getLogger(__name__)


@dataclass
class ClarificationOutcome:
    """Result container for clarification workflows."""

    success: bool
    context: Optional[Dict[str, Any]] = None


async def run_clarification_workflow(
    *,
    data: Dict[str, Any],
    settings: Dict[str, Any],
    customer_id: int,
    manager: StreamingManager,
    service: ChatService,
    completion_token: str,
) -> ClarificationOutcome:
    """Execute the clarification workflow and capture relevant context."""

    user_input = data.get("user_input", "")
    answers = data.get("answers")
    custom_details = data.get("custom_details")
    auto_enhance = data.get("auto_enhance", False)
    auto_generate_images = data.get("auto_generate_images", False)
    timings: Dict[str, float] = {}
    timings["start_time"] = time.time()

    cancelled = False

    try:
        if not user_input:
            await manager.send_to_queues(
                {
                    "type": "error",
                    "content": "Original user input required for clarification response",
                    "stage": "clarification",
                }
            )
            return ClarificationOutcome(success=False)

        result = await handle_clarification_workflow(
            user_input=user_input,
            answers=answers,
            custom_details=custom_details,
            auto_enhance=auto_enhance,
            auto_generate_images=auto_generate_images,
            settings=settings,
            customer_id=customer_id,
            manager=manager,
            service=service,
            timings=timings,
        )

        context = {
            "answers": answers,
            "auto_enhance": auto_enhance,
            "auto_generate_images": auto_generate_images,
            "result_keys": list(result.keys()),
        }
        return ClarificationOutcome(success=True, context=context)
    except asyncio.CancelledError:
        logger.info(
            "Clarification workflow cancelled (customer=%s)", customer_id
        )
        cancelled = True
        raise
    finally:
        if not cancelled:
            # Clarification workflow generates text but never TTS
            await manager.send_to_queues({"type": "text_completed", "content": ""})
            await manager.send_to_queues({"type": "tts_not_requested", "content": ""})

        await manager.signal_completion(token=completion_token)
