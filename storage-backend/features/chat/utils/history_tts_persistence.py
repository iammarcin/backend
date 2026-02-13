"""Persistence utilities for TTS-only chat workflows."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from fastapi import WebSocket
from pydantic import ValidationError as PydanticValidationError

from core.exceptions import ConfigurationError, DatabaseError
from core.streaming.manager import StreamingManager
from features.chat.schemas.requests import UpdateMessageRequest
from features.chat.schemas.message_content import MessagePatch
from features.chat.service import ChatHistoryService
from infrastructure.db.mysql import require_main_session_factory, session_scope

from .history_payloads import coerce_dict
from .websocket_session import WorkflowSession

logger = logging.getLogger(__name__)


def _resolve_audio_url(tts_metadata: Dict[str, Any]) -> Optional[str]:
    audio_file_url = tts_metadata.get("audio_file_url")
    if audio_file_url:
        return audio_file_url

    storage_meta = tts_metadata.get("storage_metadata")
    if isinstance(storage_meta, dict):
        return storage_meta.get("s3_url")
    return None


async def persist_tts_only_result(
    *,
    websocket: WebSocket,
    session: WorkflowSession,
    request_data: Dict[str, Any],
    settings: Dict[str, Any],
    workflow,
    customer_id: int,
    manager: StreamingManager,
) -> None:
    """Persist a TTS result to an existing message."""

    user_input = coerce_dict(request_data.get("user_input"))
    if not user_input:
        logger.info("Skipping TTS persistence due to missing user_input payload")
        return

    message_id = user_input.get("message_id")
    if not message_id:
        logger.warning(
            "TTS request missing message_id, cannot update message. "
            "session_id=%s, customer_id=%s, user_input_keys=%s",
            session.session_id,
            customer_id,
            list(user_input.keys()) if user_input else None,
        )
        await manager.send_event(
            {
                "type": "error",
                "stage": "database",
                "content": "TTS request requires message_id",
                "session_id": session.session_id,
            }
        )
        return

    tts_metadata = workflow.result.get("tts") or {}
    audio_file_url = _resolve_audio_url(tts_metadata)
    if not audio_file_url:
        logger.warning("TTS workflow completed but no audio file URL available")
        return

    try:
        patch_data = {
            "file_locations": [audio_file_url],
            "api_tts_gen_model_name": tts_metadata.get("model"),
        }
        patch = MessagePatch(**patch_data)
        request_model = UpdateMessageRequest(
            customer_id=customer_id,
            message_id=int(message_id),
            patch=patch,
            append_image_locations=False,
        )
    except PydanticValidationError as exc:
        logger.error(
            "Failed to build TTS update request: %s. "
            "message_id=%s, customer_id=%s, session_id=%s, patch_data=%s",
            exc,
            message_id,
            customer_id,
            session.session_id,
            patch_data,
        )
        await manager.send_event(
            {
                "type": "error",
                "stage": "database",
                "content": "Invalid TTS update payload",
                "session_id": session.session_id,
            }
        )
        return

    try:
        session_factory = require_main_session_factory()
    except ConfigurationError as exc:
        logger.error("Chat database not configured: %s", exc)
        await manager.send_event(
            {
                "type": "error",
                "stage": "database",
                "content": "Chat database not configured",
                "session_id": session.session_id,
            }
        )
        return

    try:
        async with session_scope(session_factory) as db_session:
            service = ChatHistoryService(db_session)
            result = await service.update_message(request_model)
        result_payload = result.model_dump()
    except (DatabaseError, PydanticValidationError) as exc:
        logger.error("Failed to update message with TTS audio: %s", exc)
        await manager.send_event(
            {
                "type": "error",
                "stage": "database",
                "content": "Failed to update message with TTS audio",
                "session_id": session.session_id,
            }
        )
        return
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Unexpected error updating message: %s", exc, exc_info=True)
        await manager.send_event(
            {
                "type": "error",
                "stage": "database",
                "content": "Unexpected error updating message",
                "session_id": session.session_id,
            }
        )
        return

    logger.info(
        "Updated message %s with TTS audio for customer %s",
        message_id,
        customer_id,
    )

    await manager.send_event(
        {
            "type": "db_operation_executed",
            "content": json.dumps(result_payload),
            "session_id": session.session_id,
        }
    )
    return


__all__ = ["persist_tts_only_result"]
