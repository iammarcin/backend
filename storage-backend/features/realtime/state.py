from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from time import perf_counter


class TurnPhase(str, Enum):
    """Enumerate the high-level phases for a realtime conversational turn."""

    IDLE = "idle"
    USER_SPEAKING = "user_speaking"
    AI_THINKING = "ai_thinking"
    AI_RESPONDING = "ai_responding"
    PERSISTING = "persisting"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERRORED = "errored"


@dataclass(slots=True)
class RealtimeTurnState:
    """Track realtime turn lifecycle and completion requirements."""

    phase: TurnPhase = TurnPhase.IDLE
    response_id: str | None = None

    error_code: str | None = None
    error_severity: str | None = None
    error_requires_close: bool = True

    # Completion flags populated from provider events
    has_user_transcript: bool = False
    has_ai_text: bool = False
    has_ai_audio: bool = False
    response_done: bool = False
    cancelled: bool = False

    # Expected modalities for the active session
    expect_user_transcript: bool = False
    expect_ai_text: bool = True
    expect_ai_audio: bool = False

    _turn_started_at: float | None = None
    _turn_completed_at: float | None = None

    def configure_for_modalities(
        self,
        *,
        audio_output_enabled: bool,
        text_output_enabled: bool,
        audio_input_enabled: bool,
    ) -> None:
        """Configure which artefacts are required for the current session."""

        self.expect_ai_audio = audio_output_enabled
        self.expect_ai_text = text_output_enabled
        self.expect_user_transcript = audio_input_enabled

    def start_user_turn(self) -> None:
        """Mark that the user has started providing input."""

        if self.phase is TurnPhase.IDLE:
            self._turn_started_at = perf_counter()
        if self.phase not in {TurnPhase.PERSISTING, TurnPhase.COMPLETED}:
            self.phase = TurnPhase.USER_SPEAKING

    def start_ai_processing(self) -> None:
        """Transition into the provider processing phase."""

        if self.phase not in {TurnPhase.PERSISTING, TurnPhase.COMPLETED}:
            self.phase = TurnPhase.AI_THINKING

    def start_ai_response(self, response_id: str | None) -> None:
        """Record that the provider has started responding."""

        if response_id:
            self.response_id = response_id
        if self.phase not in {TurnPhase.PERSISTING, TurnPhase.COMPLETED}:
            self.phase = TurnPhase.AI_RESPONDING

    def mark_response_done(self) -> None:
        """Record that the provider signalled the response is complete."""

        self.response_done = True

    def mark_cancelled(self) -> None:
        """Record that the current turn was cancelled by the client or provider."""

        self.cancelled = True
        self.phase = TurnPhase.CANCELLED
        self._turn_completed_at = perf_counter()

    def is_turn_complete(self) -> bool:
        """Return ``True`` once all required artefacts for the turn are present."""

        if self.cancelled or self.phase in {TurnPhase.PERSISTING, TurnPhase.COMPLETED}:
            return False

        if not self.response_done:
            return False

        if self.expect_user_transcript and not self.has_user_transcript:
            return False

        has_required_ai_output = False
        if self.expect_ai_text and self.has_ai_text:
            has_required_ai_output = True
        if self.expect_ai_audio and self.has_ai_audio:
            has_required_ai_output = True

        if not (self.expect_ai_text or self.expect_ai_audio):
            has_required_ai_output = True

        return has_required_ai_output

    def start_persisting(self) -> None:
        """Enter the persistence phase for the current turn."""

        self.phase = TurnPhase.PERSISTING
        if self._turn_completed_at is None:
            self._turn_completed_at = perf_counter()

    def mark_completed(self) -> None:
        """Mark the turn as fully processed and persisted."""

        self.phase = TurnPhase.COMPLETED
        if self._turn_completed_at is None:
            self._turn_completed_at = perf_counter()

    def mark_error(
        self,
        error_code: str | None = None,
        severity: str | None = None,
        should_close: bool | None = None,
    ) -> None:
        """Transition the turn into an errored state."""

        self.phase = TurnPhase.ERRORED
        self.error_code = error_code
        self.error_severity = severity or "fatal"
        self.error_requires_close = True if should_close is None else should_close
        self._turn_completed_at = perf_counter()

    def reset(self) -> None:
        """Reset state in preparation for the next conversational turn."""

        self.phase = TurnPhase.IDLE
        self.response_id = None
        self.has_user_transcript = False
        self.has_ai_text = False
        self.has_ai_audio = False
        self.response_done = False
        self.cancelled = False
        self.error_code = None
        self.error_severity = None
        self.error_requires_close = True
        self._turn_started_at = None
        self._turn_completed_at = None

    def get_turn_duration_ms(self) -> float | None:
        """Return the duration of the completed turn in milliseconds."""

        if self._turn_started_at is None or self._turn_completed_at is None:
            return None
        return (self._turn_completed_at - self._turn_started_at) * 1000


__all__ = ["RealtimeTurnState", "TurnPhase"]

