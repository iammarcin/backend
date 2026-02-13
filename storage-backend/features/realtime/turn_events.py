from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import WebSocket

if TYPE_CHECKING:
    from .audio_finaliser import AudioProcessingResult
    from .event_factory import RealtimeEventFactory


async def emit_turn_events(
    *,
    factory: "RealtimeEventFactory",
    websocket: WebSocket,
    turn_number: int,
    user_message_text: str,
    assistant_message_text: str,
    audio_result: "AudioProcessingResult",
    next_audio_filename: str | None,
    write_result,
) -> None:
    import logging

    logger = logging.getLogger(__name__)

    turn_completed_event = factory.turn_completed(
        turn_number=turn_number,
        audio_filename=next_audio_filename or None,
        user_transcript=user_message_text,
        ai_transcript=assistant_message_text,
        has_audio=bool(audio_result.audio_url),
        duration_ms=None,
    )
    logger.info(
        "Sending turn.completed event (turn=%d, audio_filename='%s')",
        turn_number,
        next_audio_filename or "",
    )
    await websocket.send_text(turn_completed_event.model_dump_json(by_alias=True))

    turn_persisted_event = factory.turn_persisted(
        turn_number=turn_number,
        user_message_id=str(write_result.messages.user_message_id),
        ai_message_id=str(write_result.messages.ai_message_id),
        audio_url=audio_result.audio_url,
    )
    await websocket.send_text(turn_persisted_event.model_dump_json(by_alias=True))


__all__ = ["emit_turn_events"]
