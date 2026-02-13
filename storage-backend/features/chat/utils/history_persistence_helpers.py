"""Shared helpers for chat history persistence workflows."""

from __future__ import annotations

from typing import Any, Dict, Optional
from features.chat.schemas.requests import CreateMessageRequest, EditMessageRequest
from features.chat.service import ChatHistoryService
from infrastructure.db.mysql import session_scope


async def execute_history_call(
    *,
    session_factory,
    request_model: CreateMessageRequest | EditMessageRequest,
    is_edit: bool,
) -> Dict[str, Any]:
    """Persist a history request with an isolated DB session."""

    async with session_scope(session_factory) as db_session:
        service = ChatHistoryService(db_session)
        if is_edit:
            payload = await service.edit_message(request_model)  # type: ignore[arg-type]
        else:
            payload = await service.create_message(request_model)  # type: ignore[arg-type]
    return payload.model_dump()


def ensure_baseline_timings(timings: Optional[Dict[str, float]]) -> Dict[str, float]:
    """Guarantee that downstream timing math has a start reference."""

    resolved = dict(timings or {})
    if "start_time" not in resolved:
        baseline = resolved.get("text_request_sent_time", 0.0)
        resolved["start_time"] = baseline
    return resolved


def extract_transcription(
    workflow,
    request_data: Dict[str, Any],
    user_input: Dict[str, Any],
) -> Optional[str]:
    """Return any transcription captured during the audio workflow."""

    candidate = (
        workflow.result.get("user_transcript")
        or workflow.result.get("transcription")
        or request_data.get("transcription")
        or request_data.get("transcript")
        or user_input.get("transcription")
        or user_input.get("transcript")
    )
    if not candidate:
        return None
    value = str(candidate).strip()
    return value or None


__all__ = [
    "ensure_baseline_timings",
    "execute_history_call",
    "extract_transcription",
]
