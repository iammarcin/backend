"""Settings logging helper for WebSocket chat.

Provides concise logging of user-provided settings during chat sessions.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def log_settings_summary(settings: Dict[str, Any] | None, session_id: str) -> None:
    """Log a concise summary of user-provided settings.

    Args:
        settings: User settings dict from request
        session_id: Session ID for logging
    """
    if not settings:
        logger.debug("No user settings provided (session=%s)", session_id)
        return

    summary_parts: list[str] = []

    text_settings = settings.get("text")
    if isinstance(text_settings, dict):
        text_parts: list[str] = []
        model = text_settings.get("model")
        if model:
            text_parts.append(f"model={model}")
        if "temperature" in text_settings:
            text_parts.append(f"temp={text_settings['temperature']}")
        if "max_tokens" in text_settings:
            text_parts.append(f"max_tokens={text_settings['max_tokens']}")
        if text_parts:
            summary_parts.append(f"text[{', '.join(text_parts)}]")

    tts_settings = settings.get("tts")
    if isinstance(tts_settings, dict):
        enabled = tts_settings.get("enabled", False)
        voice = tts_settings.get("voice", "unknown")
        provider = tts_settings.get("provider", "unknown")
        summary_parts.append(f"tts[enabled={enabled}, voice={voice}, provider={provider}]")

    audio_settings = settings.get("audio")
    if isinstance(audio_settings, dict):
        enabled = audio_settings.get("enabled", False)
        mode = audio_settings.get("mode", "unknown")
        summary_parts.append(f"audio[enabled={enabled}, mode={mode}]")

    reasoning_settings = settings.get("reasoning")
    if isinstance(reasoning_settings, dict):
        enabled = reasoning_settings.get("enabled", False)
        summary_parts.append(f"reasoning[enabled={enabled}]")

    if summary_parts:
        logger.info("User settings (session=%s): %s", session_id, ", ".join(summary_parts))
    else:
        logger.debug("User settings present but empty (session=%s)", session_id)
