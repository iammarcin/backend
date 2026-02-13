"""Utility functions for proactive WebSocket message handling."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from core.utils.json_serialization import sanitize_for_json

logger = logging.getLogger(__name__)


def log_message_payload(message: Dict[str, Any], session_id: str) -> None:
    """Log message payload for debugging."""
    sanitized_payload = sanitize_for_json(message)
    payload_json = json.dumps(sanitized_payload, ensure_ascii=True)
    logger.info("Proactive WS message payload (session=%s): %s", session_id, payload_json)

    tts_settings = message.get("tts_settings")
    tts_voice = tts_settings.get("voice") if isinstance(tts_settings, dict) else None
    tts_model = tts_settings.get("model") if isinstance(tts_settings, dict) else None
    tts_auto_execute = (
        tts_settings.get("tts_auto_execute") if isinstance(tts_settings, dict) else None
    )
    logger.info(
        "Proactive WS message summary (session=%s): character=%s, "
        "tts_auto_execute=%s, tts_voice=%s, tts_model=%s",
        session_id,
        message.get("ai_character_name"),
        tts_auto_execute,
        tts_voice,
        tts_model,
    )


def resolve_session_id(message: Dict[str, Any], url_session_id: str) -> str | None:
    """Determine effective session_id from message or URL parameter.

    - If message has "session_id" key with non-null value: use that session
    - If message has "session_id" key with null value: create NEW session (don't use URL)
    - If message has no "session_id" key: use URL parameter (backward compat)
    """
    has_key = "session_id" in message
    msg_session_id = message.get("session_id") if has_key else None
    
    if has_key:
        result = msg_session_id if msg_session_id else None
    else:
        result = url_session_id
    
    logger.info(
        "[SESSION DEBUG] resolve_session_id: has_key=%s, msg_session=%s, url_session=%s -> result=%s",
        has_key,
        msg_session_id[:8] if msg_session_id else "none",
        url_session_id[:8] if url_session_id else "none",
        result[:8] if result else "none",
    )
    return result


def parse_attachments(attachments_raw: Dict[str, Any]) -> list[Dict[str, Any]]:
    """Parse attachment data from WebSocket message."""
    if not isinstance(attachments_raw, dict):
        return []

    attachments = []
    image_locations = attachments_raw.get("image_locations") or []
    file_locations = attachments_raw.get("file_locations") or []

    if isinstance(image_locations, list):
        for url in image_locations[:5]:
            if url and isinstance(url, str):
                filename = url.split("/")[-1] if "/" in url else "image"
                attachments.append({"type": "image", "url": url, "filename": filename})

    if isinstance(file_locations, list):
        remaining_slots = max(0, 5 - len(attachments))
        for url in file_locations[:remaining_slots]:
            if url and isinstance(url, str):
                filename = url.split("/")[-1] if "/" in url else "file"
                attachments.append({"type": "document", "url": url, "filename": filename})

    return attachments


async def save_user_message(
    *,
    user_id: int,
    session_id: str,
    content: str,
    source_str: str,
    ai_character_name: str,
    attachments: list[Dict[str, Any]],
):
    """Save user message to database before routing."""
    from features.proactive_agent.dependencies import get_db_session_direct
    from features.proactive_agent.repositories import ProactiveAgentRepository

    try:
        async with get_db_session_direct() as db:
            repository = ProactiveAgentRepository(db)

            # Ensure session exists with correct ai_character_name
            await repository.get_or_create_session(
                user_id=user_id,
                session_id=session_id,
                ai_character_name=ai_character_name,
            )

            image_locs = None
            file_locs = None
            if attachments:
                image_locs = [a.get("url") for a in attachments if a.get("type") == "image" and a.get("url")]
                file_locs = [a.get("url") for a in attachments if a.get("type") == "document" and a.get("url")]

            user_message = await repository.create_message(
                session_id=session_id,
                customer_id=user_id,
                direction="user_to_agent",
                content=content,
                source=source_str,
                ai_character_name=ai_character_name,
                image_locations=image_locs if image_locs else None,
                file_locations=file_locs if file_locs else None,
            )
            logger.debug(
                "Saved user message: session=%s, message_id=%s",
                session_id[:8],
                user_message.message_id,
            )
            return user_message
    except Exception as e:
        logger.error("Failed to save user message: %s", e)
        return None
