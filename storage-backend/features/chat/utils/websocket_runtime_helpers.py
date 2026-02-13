"""Runtime helpers for WebSocket endpoint.

Extracted from websocket.py to maintain file size discipline (< 250 lines).
These helpers manage runtime cleanup and audio frame routing.
"""

import asyncio
import json
import logging
from contextlib import suppress
from typing import Any, Dict, Optional

from features.audio.deepgram_helpers import parse_control_message
from features.chat.utils.websocket_runtime import WorkflowRuntime

logger = logging.getLogger(__name__)


async def cleanup_runtime(runtime: Optional[WorkflowRuntime]) -> None:
    """Close audio queues and await runtime tasks safely.

    Tasks (like send_to_frontend) complete naturally after signal_completion
    puts None on the queue. We only cancel if the runtime was explicitly
    cancelled by user abort - otherwise tasks finish processing their queues.
    """

    if runtime is None:
        return

    runtime.close_audio_queue()
    tasks = list(runtime.tasks)
    if not tasks:
        return

    # Only cancel tasks on explicit user abort. For normal completion,
    # tasks finish when they process the None sentinel from signal_completion.
    if runtime.is_cancelled():
        for task in tasks:
            if task.done():
                continue
            task.cancel()

    with suppress(Exception):
        await asyncio.gather(*tasks, return_exceptions=True)


async def route_audio_frame_if_needed(
    message: Dict[str, Any],
    *,
    runtime: Optional[WorkflowRuntime],
    session_id: str,
) -> bool:
    """Push audio frames into the runtime queue when an audio workflow is active."""

    if runtime is None:
        return False

    queue = runtime.get_audio_queue()
    if queue is None:
        return False

    if not is_audio_stream_frame(message):
        return False

    try:
        await runtime.enqueue_audio_message(message)
    except RuntimeError:
        logger.warning(
            "Audio frame received but runtime not initialised properly (session=%s)",
            session_id,
        )
        return False

    return True


def is_audio_stream_frame(message: Dict[str, Any]) -> bool:
    """Return True if the ASGI message should be routed to the audio queue."""

    if message.get("bytes") is not None:
        return True

    text_data = message.get("text")
    if not text_data:
        return False

    try:
        payload = json.loads(text_data)
    except json.JSONDecodeError:
        payload = {"type": text_data}

    msg_type = str(payload.get("type", "")).lower()
    if msg_type == "audio_chunk":
        return True

    control = parse_control_message(payload)
    return control == "stop"
