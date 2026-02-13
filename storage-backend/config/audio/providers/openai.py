"""OpenAI audio transcription configuration."""

from __future__ import annotations

from typing import Dict, Mapping

# Model defaults
DEFAULT_TRANSCRIBE_MODEL = "gpt-4o-transcribe"
DEFAULT_TRANSLATE_MODEL = "whisper-1"

# Streaming settings
CHUNK_SIZE = 1024  # bytes


def _spec(
    *,
    provider_name: str = "openai",
    api_type: str = "audio_transcription",
    supports_streaming: bool = True,
    support_audio_input: bool = True,
    supports_audio_output: bool = False,
    supports_vad: bool = True,
    category: str = "transcription",
    description: str,
    context_window: int = 0,
    audio_input_cost_per_min: float | None = None,
) -> Mapping[str, object]:
    """Helper to create immutable metadata mappings."""

    payload: Dict[str, object] = {
        "provider_name": provider_name,
        "api_type": api_type,
        "support_audio_input": support_audio_input,
        "supports_audio_output": supports_audio_output,
        "supports_streaming": supports_streaming,
        "supports_vad": supports_vad,
        "category": category,
        "context_window": context_window,
        "description": description,
    }
    if audio_input_cost_per_min is not None:
        payload["audio_input_cost_per_min"] = audio_input_cost_per_min
    return payload


# Shared OpenAI transcription model specifications
AUDIO_MODEL_SPECS: Dict[str, Mapping[str, object]] = {
    "gpt-4o-transcribe": _spec(
        description="High accuracy streaming transcription with VAD.",
        audio_input_cost_per_min=0.10,
    ),
    "gpt-4o-mini-transcribe": _spec(
        description="Fast and lower-cost streaming transcription with VAD.",
        audio_input_cost_per_min=0.05,
    ),
    "whisper-1": _spec(
        supports_streaming=False,
        supports_vad=False,
        category="stt",
        description="Batch speech recognition supporting 98 languages.",
        audio_input_cost_per_min=0.006,
    ),
}

STREAMING_TRANSCRIPTION_MODEL_NAMES = tuple(
    name
    for name, spec in AUDIO_MODEL_SPECS.items()
    if spec.get("category") == "transcription"
    and spec.get("supports_streaming", False)
)

# Audio transcription model definitions (as dicts to avoid circular imports)
AUDIO_MODELS: dict[str, dict[str, object]] = {
    "gpt-4o-transcribe": {
        "model_name": "gpt-4o-transcribe",
        "provider_name": "openai",
        "api_type": "audio_transcription",
        "support_audio_input": True,
        "supports_audio_output": False,
        "supports_streaming": True,
        "supports_vad": True,
        "audio_input_cost_per_min": 0.10,
        "description": "High accuracy streaming transcription with VAD.",
        "category": "transcription",
        "context_window": 0,
    },
    "gpt-4o-mini-transcribe": {
        "model_name": "gpt-4o-mini-transcribe",
        "provider_name": "openai",
        "api_type": "audio_transcription",
        "support_audio_input": True,
        "supports_audio_output": False,
        "supports_streaming": True,
        "supports_vad": True,
        "audio_input_cost_per_min": 0.05,
        "description": "Fast and lower-cost streaming transcription with VAD.",
        "category": "transcription",
        "context_window": 0,
    },
    "whisper-1": {
        "model_name": "whisper-1",
        "provider_name": "openai",
        "api_type": "audio_transcription",
        "support_audio_input": True,
        "supports_audio_output": False,
        "supports_streaming": False,
        "supports_vad": False,
        "input_cost_per_1m": 0.006,
        "description": "Batch speech recognition supporting 98 languages.",
        "category": "stt",
        "context_window": 0,
    },
}


__all__ = [
    "DEFAULT_TRANSCRIBE_MODEL",
    "DEFAULT_TRANSLATE_MODEL",
    "CHUNK_SIZE",
    "AUDIO_MODEL_SPECS",
    "STREAMING_TRANSCRIPTION_MODEL_NAMES",
    "AUDIO_MODELS",
]
