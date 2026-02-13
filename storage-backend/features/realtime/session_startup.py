"""Helpers for bootstrapping realtime websocket sessions."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Mapping, Sequence

from features.realtime.schemas import (
    RealtimeHandshakeMessage,
    RealtimeSessionSettings,
)
from features.realtime.state import RealtimeTurnState

from .context import RealtimeTurnContext
from .utils import build_handshake, required_modalities

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SessionStartup:
    """Container for the data prepared before a session begins."""

    handshake: RealtimeHandshakeMessage
    turn_state: RealtimeTurnState
    turn_context: RealtimeTurnContext
    initial_payload: Mapping[str, object] | None
    provided_session_id: str | None
    session_modalities: Sequence[str]


def initialise_session(
    *,
    session_id: str,
    customer_id: int,
    session_defaults: RealtimeSessionSettings,
    initial_message: Mapping[str, object] | None,
) -> SessionStartup:
    """Prepare handshake, turn state, and context for a websocket session."""

    initial_payload = (
        initial_message if isinstance(initial_message, Mapping) else None
    )

    user_settings_payload = None
    if initial_payload:
        candidate = initial_payload.get("settings")
        if not isinstance(candidate, Mapping):
            candidate = initial_payload.get("user_settings")
        if isinstance(candidate, Mapping):
            user_settings_payload = candidate

    session_settings = RealtimeSessionSettings.from_user_settings(
        user_settings_payload,
        defaults=session_defaults,
    )
    session_modalities: Sequence[str] = tuple(required_modalities(session_settings))
    turn_state = RealtimeTurnState()
    turn_state.configure_for_modalities(
        audio_output_enabled=session_settings.enable_audio_output
        and session_settings.tts_auto_execute,
        text_output_enabled=session_settings.requires_text_output(),
        audio_input_enabled=session_settings.enable_audio_input,
    )
    stored_user_settings = (
        _normalise_user_settings(user_settings_payload)
        if isinstance(user_settings_payload, Mapping)
        else None
    )
    turn_context = RealtimeTurnContext(initial_user_settings=stored_user_settings)

    logger.debug(
        "Initial realtime session settings resolved",
        extra={
            "session_id": session_id,
            "model": session_settings.model,
            "vad_enabled": session_settings.vad_enabled,
            "enable_audio_input": session_settings.enable_audio_input,
            "enable_audio_output": session_settings.enable_audio_output,
        },
    )

    base_audio_filename = ""
    provided_session_id: str | None = None

    if initial_payload:
        user_input_payload = initial_payload.get("user_input")
        if isinstance(user_input_payload, Mapping):
            audio_candidate = user_input_payload.get("audio_file_name")
            if isinstance(audio_candidate, str):
                base_audio_filename = audio_candidate

            provided_candidate = user_input_payload.get("session_id")
            if isinstance(provided_candidate, str) and provided_candidate:
                provided_session_id = provided_candidate

        top_level_session = initial_payload.get("session_id")
        if (
            isinstance(top_level_session, str)
            and top_level_session
            and not provided_session_id
        ):
            provided_session_id = top_level_session

    if base_audio_filename:
        turn_context.set_base_audio_filename(base_audio_filename)
        logger.debug(
            "Configured base audio filename for realtime session",
            extra={
                "session_id": session_id,
                "base_audio_filename": base_audio_filename,
                "adjusted_audio_filename": turn_context.adjusted_audio_filename,
            },
        )

    handshake = build_handshake(
        session_id=session_id, customer_id=customer_id, settings=session_settings
    )

    return SessionStartup(
        handshake=handshake,
        turn_state=turn_state,
        turn_context=turn_context,
        initial_payload=initial_payload,
        provided_session_id=provided_session_id,
        session_modalities=session_modalities,
    )


__all__ = ["SessionStartup", "initialise_session"]


def _normalise_user_settings(source: Mapping[str, object]) -> dict[str, object]:
    """Return a JSON-compatible copy of the provided user settings mapping."""

    def _convert(value: object) -> object:
        if isinstance(value, Mapping):
            return {str(key): _convert(item) for key, item in value.items()}
        if isinstance(value, list):
            return [_convert(item) for item in value]
        if isinstance(value, tuple):
            return [_convert(item) for item in value]
        return value

    return {str(key): _convert(value) for key, value in source.items()}

