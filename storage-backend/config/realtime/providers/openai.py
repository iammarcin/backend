"""OpenAI Realtime API configuration."""

from __future__ import annotations

# Model defaults
DEFAULT_MODEL = "gpt-realtime"
DEFAULT_MODEL_ALIAS = "gpt-4o-realtime-preview"

# Audio settings
DEFAULT_SAMPLE_RATE = 24_000  # Hz
SUPPORTED_SAMPLE_RATES = [24_000]

# Voice settings
DEFAULT_VOICE = "alloy"
AVAILABLE_VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]

# Turn detection defaults
DEFAULT_TURN_DETECTION_ENABLED = True
DEFAULT_TURN_DETECTION_THRESHOLD = 0.5
DEFAULT_TURN_DETECTION_SILENCE_DURATION_MS = 500
DEFAULT_TURN_DETECTION_PREFIX_PADDING_MS = 300

# Realtime voices
REALTIME_VOICES: tuple[str, ...] = (
    "alloy",
    "ash",
    "ballad",
    "coral",
    "echo",
    "sage",
    "shimmer",
    "verse",
    "marin",
    "cedar",
)

# Realtime model definitions (as dicts to avoid circular imports)
REALTIME_MODELS: dict[str, dict[str, object]] = {
    "gpt-realtime": {
        "model_name": "gpt-realtime",
        "provider_name": "openai",
        "api_type": "realtime",
        "support_audio_input": True,
        "supports_audio_output": True,
        "supports_streaming": True,
        "supports_vad": True,
        "supports_function_calling": True,
        "voices": REALTIME_VOICES,
        "audio_input_cost_per_min": 0.10,
        "audio_output_cost_per_min": 0.20,
        "description": "High-quality realtime speech-to-speech model (GA).",
        "category": "realtime",
    },
    "gpt-realtime-mini": {
        "model_name": "gpt-realtime-mini",
        "provider_name": "openai",
        "api_type": "realtime",
        "support_audio_input": True,
        "supports_audio_output": True,
        "supports_streaming": True,
        "supports_vad": True,
        "supports_function_calling": True,
        "voices": REALTIME_VOICES,
        "audio_input_cost_per_min": 0.05,
        "audio_output_cost_per_min": 0.10,
        "description": "Fast and cost-effective realtime speech-to-speech model (GA).",
        "category": "realtime",
    },
    "gpt-realtime-preview": {
        "model_name": "gpt-realtime-preview",
        "provider_name": "openai",
        "api_type": "realtime",
        "support_audio_input": True,
        "supports_audio_output": True,
        "supports_streaming": True,
        "supports_vad": True,
        "supports_function_calling": True,
        "voices": REALTIME_VOICES,
        "audio_input_cost_per_min": 0.10,
        "audio_output_cost_per_min": 0.20,
        "description": "Low-latency realtime preview model with audio input/output support.",
        "category": "realtime",
        "is_deprecated": True,
        "replacement_model": "gpt-realtime",
    },
    "gpt-4o-realtime-preview": {
        "model_name": "gpt-4o-realtime-preview",
        "provider_name": "openai",
        "api_type": "realtime",
        "support_audio_input": True,
        "supports_audio_output": True,
        "supports_streaming": True,
        "supports_vad": True,
        "supports_function_calling": True,
        "voices": REALTIME_VOICES,
        "audio_input_cost_per_min": 0.10,
        "audio_output_cost_per_min": 0.20,
        "description": "GPT-4o realtime preview with voice support and function calling.",
        "category": "realtime",
        "is_deprecated": True,
        "replacement_model": "gpt-realtime",
    },
}

__all__ = [
    "DEFAULT_MODEL",
    "DEFAULT_MODEL_ALIAS",
    "DEFAULT_SAMPLE_RATE",
    "SUPPORTED_SAMPLE_RATES",
    "DEFAULT_VOICE",
    "AVAILABLE_VOICES",
    "DEFAULT_TURN_DETECTION_ENABLED",
    "DEFAULT_TURN_DETECTION_THRESHOLD",
    "DEFAULT_TURN_DETECTION_SILENCE_DURATION_MS",
    "DEFAULT_TURN_DETECTION_PREFIX_PADDING_MS",
    "REALTIME_VOICES",
    "REALTIME_MODELS",
]
