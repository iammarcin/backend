"""Helpers for Gemini-based audio direct workflows."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict

from core.streaming.manager import StreamingManager
from core.utils.env import is_production
from features.chat.utils.prompt_utils import PromptInput

from .gemini_audio import PreparedAudio, _convert_pcm_to_wav, prepare_audio_for_gemini
from .gemini_prompt import _extract_text_from_prompt
from .gemini_streaming import _call_gemini_multimodal_and_stream

logger = logging.getLogger(__name__)

DEFAULT_PROMPT = "Your response **must** follow the structure. First respond to whatever user says/requests (**without** any meta commentary - like you were talking to human). Only after that add short audio analysis (what can you hear on top of human voice and human voice analysis - what can you tell about human (if any) based on what you've heard)"
PRODUCTION_MODEL = "gemini-2.5-pro"
NON_PRODUCTION_MODEL = "gemini-2.5-flash"

async def _process_audio_with_gemini(
    *,
    audio_buffer: bytearray,
    prompt: PromptInput | Any,
    settings: Dict[str, Any],
    customer_id: int,
    manager: StreamingManager,
    service: Any,
    timings: Dict[str, float],
    user_input: Dict[str, Any],
) -> Dict[str, Any]:
    """Process collected audio with Gemini's multimodal LLM."""

    _ = service  # Reserved for future enhancements (database persistence hooks)

    logger.info(
        "Processing audio with Gemini multimodal LLM (audio_size=%s bytes)",
        len(audio_buffer),
    )

    try:
        prepared_audio: PreparedAudio = await prepare_audio_for_gemini(
            audio_buffer=audio_buffer,
            settings=settings,
            timings=timings,
        )

        text_prompt = _extract_text_from_prompt(prompt) or DEFAULT_PROMPT

        model_name = PRODUCTION_MODEL if is_production() else NON_PRODUCTION_MODEL
        timings["llm_request_start"] = time.time()

        result = await _call_gemini_multimodal_and_stream(
            wav_data=prepared_audio.wav_bytes,
            text_prompt=text_prompt,
            model_name=model_name,
            user_input=user_input,
            settings=settings,
            customer_id=customer_id,
            manager=manager,
            timings=timings,
        )

        timings["llm_request_end"] = time.time()
        logger.info("Audio_direct workflow completed successfully (model=%s)", model_name)

        return {
            "success": True,
            "audio_size": len(audio_buffer),
            "resampled_size": len(prepared_audio.pcm_bytes),
            "wav_size": len(prepared_audio.wav_bytes),
            "model": model_name,
            **result,
        }
    except Exception as exc:
        logger.error("Error processing audio with Gemini: %s", exc, exc_info=True)
        await manager.send_to_queues(
            {
                "type": "error",
                "content": f"Failed to process audio: {exc}",
                "stage": "gemini_multimodal",
            }
        )
        return {
            "success": False,
            "error": str(exc),
        }


async def process_audio_with_gemini(**kwargs: Any) -> Dict[str, Any]:
    """Compatibility wrapper for external callers."""

    return await _process_audio_with_gemini(**kwargs)


__all__ = [
    "PreparedAudio",
    "_process_audio_with_gemini",
    "_convert_pcm_to_wav",
    "_extract_text_from_prompt",
    "process_audio_with_gemini",
    "prepare_audio_for_gemini",
    "_call_gemini_multimodal_and_stream",
]

