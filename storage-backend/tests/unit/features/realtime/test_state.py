from __future__ import annotations

from features.realtime.state import RealtimeTurnState, TurnPhase


def test_turn_state_reaches_completed_phase_when_requirements_met() -> None:
    state = RealtimeTurnState()
    state.configure_for_modalities(
        audio_output_enabled=False,
        text_output_enabled=True,
        audio_input_enabled=True,
    )

    state.start_user_turn()
    state.has_user_transcript = True
    state.start_ai_response(response_id="resp-1")
    state.has_ai_text = True
    state.mark_response_done()

    assert state.is_turn_complete() is True

    state.start_persisting()
    state.mark_completed()

    assert state.phase is TurnPhase.COMPLETED
    assert state.get_turn_duration_ms() is not None


def test_turn_state_cancel_prevents_completion() -> None:
    state = RealtimeTurnState()
    state.configure_for_modalities(
        audio_output_enabled=True,
        text_output_enabled=False,
        audio_input_enabled=True,
    )

    state.start_user_turn()
    state.mark_cancelled()

    assert state.is_turn_complete() is False
    assert state.phase is TurnPhase.CANCELLED

    state.reset()
    assert state.phase is TurnPhase.IDLE
