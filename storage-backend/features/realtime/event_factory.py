"""Helpers for constructing realtime websocket events."""

from __future__ import annotations

from .errors import RealtimeError
from .schemas import (
    SessionClosedEvent,
    TurnCompletedEvent,
    TurnPersistedEvent,
    RealtimeErrorEvent,
)


class RealtimeEventFactory:
    """Factory for building realtime websocket events with shared session metadata."""

    def __init__(self, *, session_id: str) -> None:
        self._session_id = session_id

    def turn_completed(
        self,
        *,
        turn_number: int,
        audio_filename: str | None,
        user_transcript: str,
        ai_transcript: str,
        has_audio: bool,
        duration_ms: float | None,
    ) -> TurnCompletedEvent:
        return TurnCompletedEvent(
            session_id=self._session_id,
            turn_number=turn_number,
            audio_filename=audio_filename,
            user_transcript=user_transcript,
            ai_transcript=ai_transcript,
            has_audio=has_audio,
            duration_ms=duration_ms,
        )

    def turn_persisted(
        self,
        *,
        turn_number: int,
        user_message_id: str,
        ai_message_id: str,
        audio_url: str | None,
    ) -> TurnPersistedEvent:
        return TurnPersistedEvent(
            session_id=self._session_id,
            turn_number=turn_number,
            user_message_id=user_message_id,
            ai_message_id=ai_message_id,
            audio_url=audio_url,
        )

    def session_closed(
        self,
        *,
        total_turns: int,
        total_duration_ms: float,
    ) -> SessionClosedEvent:
        return SessionClosedEvent(
            session_id=self._session_id,
            total_turns=total_turns,
            total_duration_ms=total_duration_ms,
        )

    def error_from_realtime_error(
        self,
        error: RealtimeError,
        *,
        turn_number: int | None = None,
    ) -> RealtimeErrorEvent:
        payload: dict[str, object] = {
            "session_id": self._session_id,
            "code": error.code.value,
            "message": error.user_message,
            "recoverable": error.recoverable,
            "details": error.details or {},
        }
        if turn_number is not None:
            payload["turn_number"] = turn_number
        return RealtimeErrorEvent.model_validate(payload)


__all__ = ["RealtimeEventFactory"]
