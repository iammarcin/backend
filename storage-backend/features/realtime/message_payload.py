"""Builders for realtime persistence payloads."""

from __future__ import annotations

import logging
from collections.abc import Mapping

from features.chat.schemas.requests import CreateMessageRequest, MessageContent
from features.realtime.schemas import RealtimeSessionSettings


logger = logging.getLogger(__name__)


def build_realtime_message_request(
    *,
    customer_id: int,
    session_name: str,
    settings: RealtimeSessionSettings,
    user_message_text: str,
    assistant_message_text: str,
    response_id: str | None,
    audio_url: str | None,
    derived_filename: str | None,
    translation_text: str | None,
    session_id: str | None,
    original_user_settings: Mapping[str, object] | None,
) -> CreateMessageRequest:
    """Create the persistence request for a realtime turn."""

    ai_character_name = _extract_ai_character(original_user_settings)
    user_settings_payload = _build_user_settings_payload(
        settings=settings,
        translation_text=translation_text,
        original_settings=original_user_settings,
    )

    message_request = CreateMessageRequest(
        customer_id=customer_id,
        session_id=session_id,
        session_name=session_name,
        ai_character_name=ai_character_name,
        ai_text_gen_model=settings.model,
        auto_trigger_tts=settings.tts_auto_execute,
        user_message=MessageContent(
            sender="User",
            message=user_message_text,
            api_text_gen_settings={
                "mode": "realtime",
                "modalities": settings.modalities(),
            },
            file_names=[derived_filename] if derived_filename else [],
        ),
        ai_response=MessageContent(
            sender="AI",
            message=assistant_message_text,
            ai_character_name=ai_character_name,
            api_text_gen_ai_model_name=settings.model,
            api_text_gen_settings={
                "mode": "realtime",
                "response_id": response_id,
                "modalities": settings.modalities(),
            },
            file_names=[audio_url] if audio_url else [],
        ),
        user_settings=user_settings_payload,
    )

    return message_request


def _build_user_settings_payload(
    *,
    settings: RealtimeSessionSettings,
    translation_text: str | None,
    original_settings: Mapping[str, object] | None,
) -> dict[str, object]:
    """Merge realtime settings with original user preferences."""

    base: dict[str, object] = {}
    if isinstance(original_settings, Mapping):
        base = _deep_copy_mapping(original_settings)

    # Use canonical snake_case keys only
    text_settings = original_settings.get("text") if isinstance(original_settings, Mapping) else None
    if isinstance(text_settings, Mapping):
        base["text"] = _deep_copy_mapping(text_settings)

    speech_raw = original_settings.get("speech") if isinstance(original_settings, Mapping) else None
    speech_settings = speech_raw if isinstance(speech_raw, Mapping) else None
    base["speech"] = _compose_speech_settings(
        settings=settings,
        translation_text=translation_text,
        existing_settings=speech_settings,
    )

    return base


def _compose_speech_settings(
    *,
    settings: RealtimeSessionSettings,
    translation_text: str | None,
    existing_settings: Mapping[str, object] | None,
) -> dict[str, object]:
    """Combine derived speech settings with any existing payload."""

    merged: dict[str, object] = {}
    if isinstance(existing_settings, Mapping):
        merged = _deep_copy_mapping(existing_settings)

    merged.update(
        {
            "voice": settings.voice,
            "temperature": settings.temperature,
            "vad_enabled": settings.vad_enabled,
            "enable_audio_output": settings.enable_audio_output,
            "tts_auto_execute": settings.tts_auto_execute,
            "live_translation": settings.live_translation,
            "translation_language": settings.translation_language,
            "live_translation_text": translation_text,
        }
    )
    return merged


def _extract_ai_character(
    settings: Mapping[str, object] | None,
) -> str | None:
    """Return the configured AI character name if provided.

    Uses canonical snake_case field names only (text, ai_character).
    """
    if not isinstance(settings, Mapping):
        logger.debug("No settings found while extracting ai_character")
        return None

    text_settings = settings.get("text")
    if not isinstance(text_settings, Mapping):
        logger.debug("No text settings found while extracting ai_character")
        return None

    candidate = text_settings.get("ai_character")
    if isinstance(candidate, str):
        candidate = candidate.strip()
        if candidate:
            return candidate

    logger.debug("ai_character not present in provided text settings")
    return None


def _extract_mapping(
    source: Mapping[str, object] | None, *keys: str
) -> Mapping[str, object] | None:
    """Return the first mapping value found for the provided keys."""

    if not isinstance(source, Mapping):
        return None
    for key in keys:
        candidate = source.get(key)
        if isinstance(candidate, Mapping):
            return candidate
    return None


def _deep_copy_mapping(source: Mapping[str, object]) -> dict[str, object]:
    """Recursively copy a mapping preserving JSON-compatible values."""

    def _convert(value: object) -> object:
        if isinstance(value, Mapping):
            return {str(key): _convert(item) for key, item in value.items()}
        if isinstance(value, list):
            return [_convert(item) for item in value]
        if isinstance(value, tuple):
            return [_convert(item) for item in value]
        return value

    return {str(key): _convert(value) for key, value in source.items()}


__all__ = ["build_realtime_message_request"]
