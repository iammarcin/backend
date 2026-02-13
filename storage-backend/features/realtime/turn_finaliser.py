from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from fastapi import WebSocket

from core.streaming.manager import StreamingManager
from features.audio.service import STTService
from features.chat.service import ChatHistoryService
from features.realtime.schemas import RealtimeSessionSettings
from features.realtime.state import RealtimeTurnState
from infrastructure.aws.storage import StorageService

from .audio_finaliser import AudioProcessingResult, RealtimeAudioFinaliser
from .context import RealtimeTurnContext
from .event_factory import RealtimeEventFactory
from .session_tracker import SessionTracker
from .turn_finaliser_workflow import perform_turn_finalisation


@dataclass(slots=True)
class TurnFinaliser:
    """Coordinate turn persistence, audio upload, and optional translation."""

    chat_history_service: ChatHistoryService
    storage_service_factory: Callable[[], StorageService]
    streaming_manager: StreamingManager
    stt_service_factory: Callable[[], STTService]
    session_tracker: SessionTracker
    event_factory: RealtimeEventFactory
    _audio_finaliser: RealtimeAudioFinaliser | None = field(default=None, init=False)

    async def finalise_turn(
        self,
        *,
        customer_id: int,
        settings: RealtimeSessionSettings,
        turn_state: RealtimeTurnState,
        turn_context: RealtimeTurnContext,
        websocket: WebSocket,
        session_id: str,
        event_factory: RealtimeEventFactory,
    ) -> None:
        await perform_turn_finalisation(
            self,
            customer_id=customer_id,
            settings=settings,
            turn_state=turn_state,
            turn_context=turn_context,
            websocket=websocket,
            session_id=session_id,
            event_factory=event_factory,
        )

    def _assistant_text(
        self,
        *,
        assistant_text: str | None,
        audio_result: AudioProcessingResult,
    ) -> str:
        if assistant_text:
            return assistant_text
        if audio_result.audio_url:
            return "[Voice response]"
        return "[No response]"

    async def _process_audio(
        self,
        *,
        turn_context: RealtimeTurnContext,
        settings: RealtimeSessionSettings,
        websocket: WebSocket,
        session_id: str,
        customer_id: int,
    ) -> AudioProcessingResult:
        return await self._audio_finaliser_instance().process_audio(
            turn_context=turn_context,
            settings=settings,
            websocket=websocket,
            session_id=session_id,
            customer_id=customer_id,
        )

    def _audio_finaliser_instance(self) -> RealtimeAudioFinaliser:
        if self._audio_finaliser is None:
            self._audio_finaliser = RealtimeAudioFinaliser(
                storage_service_factory=self.storage_service_factory,
                stt_service_factory=self.stt_service_factory,
                streaming_manager=self.streaming_manager,
                event_factory=self.event_factory,
            )
        return self._audio_finaliser


__all__ = ["TurnFinaliser"]
