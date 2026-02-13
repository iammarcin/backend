"""REST API routes for audio processing."""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import JSONResponse

from core.auth import AuthContext, require_auth_context
from core.pydantic_schemas import ApiResponse, error as api_error, ok as api_ok
from core.exceptions import ServiceError
from features.audio.dependencies import (
    ParsedStaticTranscription,
    get_stt_service,
    parse_static_transcription_form,
)
from features.audio.schemas import StaticTranscriptionResponse
from features.audio.service import STTService
from features.proactive_agent.openclaw.config import is_openclaw_enabled
from features.proactive_agent.openclaw.router import send_message_to_openclaw
from services.temporary_storage import persist_upload_file

logger = logging.getLogger(__name__)


async def _handle_offline_sherlock_sync(
    transcription: str,
    metadata: dict[str, Any],
    user_id: int,
) -> Optional[str]:
    """Handle offline Sherlock audio sync.

    1. Build batch header based on position in batch
    2. Route to OpenClaw Gateway
    3. Return session_id
    """
    if not is_openclaw_enabled():
        raise RuntimeError("OpenClaw is not enabled on this server")

    from uuid import uuid4

    ai_character_name = metadata.get("ai_character_name", "sherlock")
    session_id = metadata.get("session_id") or str(uuid4())  # Generate if first message
    batch_index = metadata.get("batch_index", 1)
    batch_total = metadata.get("batch_total", 1)
    recorded_at = metadata.get("recorded_at", "earlier")

    # Build message content with batch header
    if batch_total > 1 and batch_index < batch_total:
        # More messages coming - ask for brief ACK
        header = f"""---
Offline audio {batch_index}/{batch_total} (recorded {recorded_at}).
More offline messages are queued. Please ACK this one briefly and wait for the next.
---

"""
    elif batch_total > 1 and batch_index == batch_total:
        # Last message in batch
        header = f"""---
Offline audio {batch_index}/{batch_total} (recorded {recorded_at}). This is the last offline message.
You can respond normally.
---

"""
    else:
        # Single offline message
        header = f"""---
[Recorded while offline: {recorded_at}]
---

"""

    content = header + transcription

    result = await send_message_to_openclaw(
        user_id=user_id,
        session_id=session_id,
        message=content,
        ai_character_name=ai_character_name,
        tts_settings=None,  # No TTS for offline sync
    )

    return result.get("session_id", session_id)

router = APIRouter(prefix="/api/v1/audio", tags=["Audio"])


@router.post(
    "/transcribe",
    summary="Transcribe a static audio recording",
    response_model=ApiResponse[StaticTranscriptionResponse],
)
async def transcribe_audio_endpoint(
    file: UploadFile = File(..., description="Audio file to transcribe"),
    parsed: ParsedStaticTranscription = Depends(parse_static_transcription_form),
    auth_context: AuthContext = Depends(require_auth_context),
    service: STTService = Depends(get_stt_service),
) -> JSONResponse:
    """Accept multipart uploads and return a transcription envelope."""

    logger.debug(
        "Authenticated static transcription request (customer_id=%s)",
        auth_context["customer_id"],
    )

    if parsed.errors:
        logger.debug("Static transcription payload validation failed: %s", parsed.errors)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=api_error(
                400,
                "Invalid static transcription payload",
                data={"errors": parsed.errors},
            ),
        )

    assert parsed.request is not None  # ``parsed.errors`` handled above
    request = parsed.request

    stored_file = await persist_upload_file(
        file,
        customer_id=request.customer_id,
        category="audio",
        prefix="static_",
    )
    logger.info(
        "Stored static transcription upload", extra={"path": str(stored_file.path)}
    )

    try:
        result = await service.transcribe_file(
            action=request.action,
            customer_id=request.customer_id,
            file_path=stored_file.path,
            filename=stored_file.filename,
            content_type=stored_file.content_type,
            user_input=request.user_input,
            user_settings=request.user_settings,
        )
    except ServiceError as exc:
        logger.error("Static transcription service error: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content=api_error(502, str(exc)),
        )
    finally:
        await file.close()

    # Check if this is an offline Sherlock sync request
    # user_input is a Pydantic model with extra="allow", so extra fields are in model_extra
    offline_sync_meta = (request.user_input.model_extra or {}).get(
        "offline_sherlock_sync_metadata"
    )
    if offline_sync_meta:
        try:
            session_id = await _handle_offline_sherlock_sync(
                transcription=result.result,
                metadata=offline_sync_meta,
                user_id=auth_context["customer_id"],
            )
            logger.info(
                "Offline Sherlock sync processed",
                extra={
                    "user_id": auth_context["customer_id"],
                    "session_id": session_id,
                    "batch_index": offline_sync_meta.get("batch_index"),
                    "batch_total": offline_sync_meta.get("batch_total"),
                },
            )
            # Return enhanced response for offline sync
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=api_ok(
                    "Offline transcription sync completed",
                    data={
                        "transcription": result.result,
                        "session_id": session_id,
                        "offline_sync_processed": True,
                        "provider": result.provider,
                        "language": result.language,
                    },
                ),
            )
        except Exception as exc:
            logger.error("Offline Sherlock sync failed: %s", exc, exc_info=True)
            # Return transcription even if sync fails, so Kotlin can retry
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=api_ok(
                    "Transcription completed (sync failed)",
                    data={
                        "transcription": result.result,
                        "session_id": None,
                        "offline_sync_processed": False,
                        "sync_error": str(exc),
                        "provider": result.provider,
                        "language": result.language,
                    },
                ),
            )

    payload = StaticTranscriptionResponse(
        status=result.status,
        result=result.result,
        action=result.action,
        provider=result.provider,
        filename=result.filename,
        language=result.language,
    )
    response = api_ok(
        "Transcription completed",
        data=payload.model_dump(by_alias=True, exclude_none=True),
        meta={
            "filename": result.filename,
            "provider": result.provider,
            "language": result.language,
            "metadata": result.metadata,
        },
    )
    return JSONResponse(status_code=status.HTTP_200_OK, content=response)


__all__ = ["router"]
