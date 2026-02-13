"""Utilities for translating user provided realtime settings payloads."""

from __future__ import annotations

import logging
from typing import Mapping, TYPE_CHECKING

from features.chat.utils.system_prompt import resolve_system_prompt

logger = logging.getLogger(__name__)
_TRUTHY = {"1", "true", "yes", "on"}
_FALSEY = {"0", "false", "no", "off"}

if TYPE_CHECKING:  # pragma: no cover - only used for typing
    from .schemas import RealtimeSessionSettings


def build_settings_from_user_settings(
    settings_cls: type["RealtimeSessionSettings"],
    user_settings: Mapping[str, object] | None,
    *,
    defaults: "RealtimeSessionSettings" | None = None,
) -> "RealtimeSessionSettings":
    """Create ``RealtimeSessionSettings`` from user provided payload data."""

    settings = defaults.model_copy(deep=True) if defaults else settings_cls()
    if not isinstance(user_settings, Mapping):
        return settings

    # Use canonical snake_case keys only
    speech_raw = user_settings.get("speech")
    speech_settings = speech_raw if isinstance(speech_raw, Mapping) else None

    tts_raw = user_settings.get("tts")
    tts_settings = tts_raw if isinstance(tts_raw, Mapping) else None

    general_raw = user_settings.get("general")
    general_settings = general_raw if isinstance(general_raw, Mapping) else None

    # Extract model override using canonical key only
    model_override = None
    if speech_settings:
        model_candidate = speech_settings.get("model")
        if isinstance(model_candidate, str) and model_candidate.strip():
            model_override = model_candidate.strip()
    if model_override is None:
        model_candidate = user_settings.get("model")
        if isinstance(model_candidate, str) and model_candidate.strip():
            model_override = model_candidate.strip()
    if model_override:
        settings.model = model_override

    if speech_settings or tts_settings:
        _apply_speech_settings(settings, speech_settings or {}, tts_settings)

    if general_settings:
        _apply_general_settings(settings, general_settings)

    # Use canonical snake_case key only
    session_name_raw = user_settings.get("session_name")
    if isinstance(session_name_raw, str) and session_name_raw.strip():
        settings.session_name = session_name_raw.strip()

    # Resolve system prompt from ai_character setting
    if isinstance(user_settings, dict):
        system_prompt = resolve_system_prompt(user_settings)
        if system_prompt:
            settings.instructions = system_prompt
            logger.info(
                "Resolved instructions from ai_character",
                extra={
                    "ai_character": user_settings.get("text", {}).get("ai_character"),
                    "instructions_length": len(system_prompt),
                },
            )
        else:
            logger.debug("No instructions resolved from user settings")

    return settings


def _apply_speech_settings(
    settings: "RealtimeSessionSettings",
    speech_settings: Mapping[str, object],
    tts_settings: Mapping[str, object] | None = None,
) -> None:
    """Apply speech specific user settings.

    Uses canonical snake_case keys only.
    """
    # Use canonical snake_case key only
    voice_raw = speech_settings.get("voice")
    if isinstance(voice_raw, str) and voice_raw.strip():
        settings.voice = voice_raw.strip()

    temperature_override = speech_settings.get("temperature")
    settings.temperature = _coerce_float(temperature_override, settings.temperature)

    conversation_mode_value = speech_settings.get("realtime_conversation_mode")
    if conversation_mode_value is not None:
        previous = settings.vad_enabled
        settings.vad_enabled = _coerce_bool(conversation_mode_value, previous)
        logger.debug(
            "Mapped realtime conversation mode to VAD setting",
            extra={
                "realtime_conversation_mode": conversation_mode_value,
                "vad_enabled": settings.vad_enabled,
            },
        )

    enable_audio_input = speech_settings.get("enable_audio_input")
    settings.enable_audio_input = _coerce_bool(
        enable_audio_input,
        settings.enable_audio_input,
    )

    enable_audio_output = speech_settings.get("enable_audio_output")
    settings.enable_audio_output = _coerce_bool(
        enable_audio_output,
        settings.enable_audio_output,
    )

    tts_auto_execute = speech_settings.get("tts_auto_execute")
    if tts_auto_execute is None and tts_settings:
        tts_auto_execute = tts_settings.get("tts_auto_execute")
    settings.tts_auto_execute = _coerce_bool(
        tts_auto_execute,
        settings.tts_auto_execute,
    )
    logger.info(
        "Settings after parsing: tts_auto_execute=%s, enable_audio_output=%s",
        settings.tts_auto_execute,
        settings.enable_audio_output,
    )

    live_translation = speech_settings.get("live_translation")
    settings.live_translation = _coerce_bool(
        live_translation,
        settings.live_translation,
    )

    translation_language_raw = speech_settings.get("translation_language")
    translation_language = translation_language_raw.strip() if isinstance(translation_language_raw, str) else None
    if translation_language:
        settings.translation_language = translation_language


def _apply_general_settings(
    settings: "RealtimeSessionSettings", general_settings: Mapping[str, object]
) -> None:
    """Apply general user settings.

    Uses canonical snake_case keys only.
    """
    return_test_data = general_settings.get("return_test_data")
    settings.return_test_data = _coerce_bool(
        return_test_data,
        settings.return_test_data,
    )

    session_name_raw = general_settings.get("session_name")
    if isinstance(session_name_raw, str) and session_name_raw.strip():
        settings.session_name = session_name_raw.strip()


def _extract_mapping(
    source: Mapping[str, object], *keys: str
) -> Mapping[str, object] | None:
    for key in keys:
        candidate = source.get(key)
        if isinstance(candidate, Mapping):
            return candidate
    return None


def _extract_str(source: Mapping[str, object], *keys: str) -> str | None:
    for key in keys:
        value = source.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _coerce_bool(value: object, current: bool) -> bool:
    if value is None:
        return current
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in _TRUTHY:
            return True
        if lowered in _FALSEY:
            return False
    return current


def _coerce_float(value: object, current: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return current
