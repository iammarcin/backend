"""Helpers for building realtime provider settings."""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def extract_provider_settings(
    settings: Dict[str, Any], instructions: str | None = None
) -> Dict[str, Any]:
    """Extract settings needed by realtime provider from user settings."""

    logger.debug(
        "Extracting provider settings",
        extra={
            "has_instructions": bool(instructions),
            "instructions_length": len(instructions) if instructions else 0,
        },
    )

    text_settings = settings.get("text", {}) if isinstance(settings, dict) else {}
    tts_settings = settings.get("tts", {}) if isinstance(settings, dict) else {}
    speech_settings = settings.get("speech", {}) if isinstance(settings, dict) else {}

    voice = speech_settings.get("realtime_voice") or tts_settings.get("voice", "alloy")

    provider_settings = {
        "model": text_settings.get("model", "gpt-realtime"),
        "voice": voice,
        "temperature": text_settings.get("temperature", 0.8),
        "tts_auto_execute": bool(tts_settings.get("tts_auto_execute", False)),
        "enable_audio_input": True,
        "enable_audio_output": bool(tts_settings.get("tts_auto_execute", False)),
        "vad_enabled": bool(speech_settings.get("realtime_conversation_mode", False)),
    }

    if instructions:
        provider_settings["instructions"] = instructions
        logger.debug("Added instructions to provider settings")
    else:
        logger.debug("No instructions provided to add to provider settings")

    return provider_settings


__all__ = ["extract_provider_settings"]
