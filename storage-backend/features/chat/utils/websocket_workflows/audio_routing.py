"""Audio workflow routing handlers.

Routes audio transcriptions to OpenClaw Gateway unconditionally.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from core.streaming.manager import StreamingManager

logger = logging.getLogger(__name__)


async def route_to_openclaw(
    *,
    transcription: str,
    customer_id: int,
    settings: Dict[str, Any],
    ai_character_name: str,
    user_input: Optional[Dict[str, Any]],
    session_id: Optional[str],
    manager: StreamingManager,
) -> Dict[str, Any]:
    """Route transcription to OpenClaw Gateway.

    Args:
        transcription: User's transcribed message
        customer_id: User ID
        settings: User settings
        ai_character_name: Character name
        user_input: User input payload
        session_id: Session ID
        manager: Streaming manager for error events

    Returns:
        Dict with success status and result
    """
    from features.proactive_agent.openclaw.config import is_openclaw_enabled

    if not is_openclaw_enabled():
        logger.error("OpenClaw routing requested but OPENCLAW_ENABLED=false")
        await manager.send_to_queues({
            "type": "error",
            "content": "OpenClaw is not enabled on this server",
            "stage": "routing",
        })
        return {
            "success": False,
            "error": "openclaw_disabled",
            "user_transcript": transcription,
        }

    logger.info(
        "Returning transcription to frontend for OpenClaw routing (customer=%s, character=%s)",
        customer_id,
        ai_character_name,
    )

    # IMPORTANT: Do NOT send to OpenClaw here!
    # The frontend's handleVoiceTranscriptionComplete will send the message via proactive WS,
    # which allows including attachments. If we send here, the message gets sent twice
    # (once without attachments from backend, once with attachments from frontend).
    #
    # Return transcription to frontend, which will:
    # 1. Call sendMessage with attachments via proactive WebSocket
    # 2. Backend's proactive_send_handler will then route to OpenClaw with attachments
    return {
        "success": True,
        "user_transcript": transcription,
        "openclaw": True,
        "skip_backend_send": True,  # Signal that frontend handles the send
    }
