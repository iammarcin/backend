"""Audio direct workflow handlers."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, TYPE_CHECKING

from fastapi import WebSocket

from core.streaming.manager import StreamingManager
from features.chat.service import ChatService
from features.chat.utils.prompt_utils import PromptInput
from features.chat.utils.websocket_workflows.gemini import process_audio_with_gemini

if TYPE_CHECKING:  # pragma: no cover - typing-only import
    from features.chat.utils.websocket_runtime import WorkflowRuntime

logger = logging.getLogger(__name__)

async def handle_audio_direct_workflow(
    *,
    websocket: WebSocket,
    prompt: PromptInput | Any,
    settings: Dict[str, Any],
    customer_id: int,
    manager: StreamingManager,
    service: ChatService,
    timings: Dict[str, float],
    user_input: Dict[str, Any],
    runtime: "WorkflowRuntime | None" = None,
) -> Dict[str, Any]:
    """Handle audio_direct workflow by collecting audio and delegating to Gemini."""

    logger.info("Starting audio_direct workflow")

    placeholder_message = (
        "🎤 Recording audio for multimodal LLM with audio understanding..."
    )

    await manager.send_to_queues(
        {"type": "transcription", "content": placeholder_message}
    )

    user_input = _update_user_message(user_input or {}, "")

    timings["audio_collection_start"] = time.time()
    audio_buffer = bytearray()
    audio_queue = runtime.get_audio_queue() if runtime is not None else None

    try:
        while True:
            if audio_queue is not None:
                message = await audio_queue.get()
                if message is None:
                    logger.info("Audio queue closed during audio_direct collection")
                    break
            else:
                message = await websocket.receive()

            if message["type"] == "websocket.disconnect":
                logger.info("WebSocket disconnected during audio collection")
                break

            if message["type"] == "websocket.receive":
                if "text" in message:
                    data = json.loads(message["text"])

                    if data.get("type") == "RecordingFinished":
                        logger.info(
                            "Received RecordingFinished, collected %s bytes",
                            len(audio_buffer),
                        )
                        break

                    if data.get("type") == "cancel":
                        logger.info("Received cancel during audio collection")
                        raise asyncio.CancelledError(
                            "User cancelled audio collection"
                        )

                if "bytes" in message and message["bytes"] is not None:
                    chunk = message["bytes"]
                    audio_buffer.extend(chunk)

        timings["audio_collection_end"] = time.time()

        if len(audio_buffer) == 0:
            logger.warning("No audio collected in audio_direct mode")
            await manager.send_to_queues(
                {
                    "type": "error",
                    "content": "No audio data received",
                    "stage": "audio_collection",
                }
            )
            return {"success": False, "error": "No audio data"}

        logger.info(
            "Audio collection complete: %s bytes, %.2f seconds",
            len(audio_buffer),
            timings["audio_collection_end"] - timings["audio_collection_start"],
        )

        result = await process_audio_with_gemini(
            audio_buffer=audio_buffer,
            prompt=prompt,
            settings=settings,
            customer_id=customer_id,
            manager=manager,
            service=service,
            timings=timings,
            user_input=user_input,
        )

        return result
    except asyncio.CancelledError:
        logger.info("Audio direct workflow cancelled")
        raise
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Error in audio_direct workflow: %s", exc, exc_info=True)
        await manager.send_to_queues(
            {
                "type": "error",
                "content": f"Audio processing error: {exc}",
                "stage": "audio_direct",
            }
        )
        return {"success": False, "error": str(exc)}


def _update_user_message(user_input: Dict[str, Any], message: str) -> Dict[str, Any]:
    """Ensure the placeholder message is reflected in the stored prompt."""

    prompt_payload = user_input.setdefault("prompt", [])

    for item in prompt_payload:
        if item.get("type") == "text":
            item["text"] = message
            return user_input

    prompt_payload.append({"type": "text", "text": message})
    return user_input


__all__ = ["handle_audio_direct_workflow"]
