"""Helpers for TTS wiring in poller stream."""

from typing import Awaitable, Callable, Optional

from features.tts.service import TTSService

from ..repositories import ProactiveAgentRepository
from ..utils.tts_session import (
    cancel_tts_session,
    complete_tts_session,
    start_tts_session,
)

StartTTSFunc = Callable[[str, int, dict], Awaitable[None]]
CompleteTTSFunc = Callable[[str, int, object], Awaitable[Optional[str]]]
CancelTTSFunc = Callable[[str, int], Awaitable[None]]


def build_tts_handlers(
    repository: ProactiveAgentRepository,
) -> tuple[StartTTSFunc, CompleteTTSFunc, CancelTTSFunc]:
    """Create TTS handler callables for stream lifecycle."""
    tts_service = TTSService()

    async def start_tts(session_id: str, user_id: int, tts_settings: dict) -> None:
        await start_tts_session(
            session_id=session_id,
            user_id=user_id,
            tts_settings=tts_settings,
            tts_service=tts_service,
        )

    async def complete_tts(
        session_id: str,
        user_id: int,
        message: object,
    ) -> Optional[str]:
        return await complete_tts_session(
            session_id=session_id,
            user_id=user_id,
            message=message,
            update_audio_url_func=repository.update_message_audio_url,
        )

    async def cancel_tts(session_id: str, user_id: int) -> None:
        await cancel_tts_session(session_id=session_id, user_id=user_id)

    return start_tts, complete_tts, cancel_tts


__all__ = ["build_tts_handlers", "StartTTSFunc", "CompleteTTSFunc", "CancelTTSFunc"]
