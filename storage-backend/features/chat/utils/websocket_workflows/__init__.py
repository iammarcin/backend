"""WebSocket workflow handlers for chat features."""

from .audio import handle_audio_workflow, merge_transcription_with_prompt
from .audio_direct import handle_audio_direct_workflow, _update_user_message
from .gemini import (
    PreparedAudio,
    _call_gemini_multimodal_and_stream,
    _convert_pcm_to_wav,
    _extract_text_from_prompt,
    _process_audio_with_gemini,
    prepare_audio_for_gemini,
    process_audio_with_gemini,
)
from .text import handle_text_workflow
from .tts import handle_tts_workflow

__all__ = [
    "handle_audio_workflow",
    "handle_audio_direct_workflow",
    "handle_text_workflow",
    "handle_tts_workflow",
    "merge_transcription_with_prompt",
    "PreparedAudio",
    "_update_user_message",
    "_call_gemini_multimodal_and_stream",
    "_process_audio_with_gemini",
    "_convert_pcm_to_wav",
    "_extract_text_from_prompt",
    "prepare_audio_for_gemini",
    "process_audio_with_gemini",
]
