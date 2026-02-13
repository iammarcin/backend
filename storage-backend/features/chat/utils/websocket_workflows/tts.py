"""Text-to-speech websocket workflow handlers."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict

from core.exceptions import ServiceError
from core.streaming.manager import StreamingManager
from features.tts.schemas.requests import TTSUserSettings
from features.tts.service import TTSService

logger = logging.getLogger(__name__)


async def handle_tts_workflow(
    *,
    prompt: Any,
    settings: Dict[str, Any],
    customer_id: int,
    manager: StreamingManager,
    timings: Dict[str, float],
    runtime=None,
) -> Dict[str, Any]:
    """Handle TTS-only workflow (speak existing message without text generation)."""

    text_to_speak = _extract_text_to_speak(prompt)
    if not text_to_speak.strip():
        raise ServiceError("No text provided for TTS generation")

    logger.info(
        "TTS workflow initiated (customer=%s, text_length=%s)",
        customer_id,
        len(text_to_speak),
    )

    await manager.send_to_queues({"type": "text_not_requested", "content": ""})

    tts_settings_dict = settings.get("tts", {})
    general_settings_dict = settings.get("general", {})

    try:
        tts_user_settings = TTSUserSettings(
            tts=tts_settings_dict,
            general=general_settings_dict,
        )
    except Exception as exc:
        logger.error("Failed to parse TTS settings: %s", exc)
        raise ServiceError(f"Invalid TTS settings: {exc}") from exc

    tts_service = TTSService()
    timings["tts_request_sent_time"] = time.time()

    try:
        tts_metadata = await tts_service.stream_text(
            text=text_to_speak,
            customer_id=customer_id,
            user_settings=tts_user_settings,
            manager=manager,
            timings=timings,
            runtime=runtime,
        )
    except Exception as exc:
        logger.error("TTS generation failed: %s", exc, exc_info=True)
        await manager.send_to_queues(
            {"type": "error", "content": f"TTS generation failed: {exc}", "stage": "tts"}
        )
        raise

    logger.info(
        "TTS workflow completed (customer=%s, audio_url=%s)",
        customer_id,
        tts_metadata.audio_file_url or "none",
    )

    return {
        "tts": {
            "provider": tts_metadata.provider,
            "model": tts_metadata.model,
            "voice": tts_metadata.voice,
            "format": tts_metadata.format,
            "audio_file_url": tts_metadata.audio_file_url,
            "storage_metadata": tts_metadata.storage_metadata,
        },
    }


def _extract_text_to_speak(prompt: Any) -> str:
    if isinstance(prompt, list):
        for item in prompt:
            if isinstance(item, dict) and item.get("type") == "text":
                return item.get("text", "")
    elif isinstance(prompt, str):
        return prompt
    return ""


__all__ = ["handle_tts_workflow"]
