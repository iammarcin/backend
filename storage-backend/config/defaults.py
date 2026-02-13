"""Global default values for AI model configurations."""

from __future__ import annotations

# Temperature defaults
DEFAULT_TEMPERATURE = 0.1
DEFAULT_TEMPERATURE_MIN = 0.0
DEFAULT_TEMPERATURE_MAX = 2.0

# Token defaults
DEFAULT_MAX_TOKENS = 4096
DEFAULT_FILE_ATTACHED_MESSAGE_LIMIT = 3

# Reasoning defaults
DEFAULT_REASONING_EFFORT_VALUES = ["low", "medium", "high"]
DEFAULT_REASONING_EFFORT_INDEX = 1  # medium

# API defaults
DEFAULT_API_TYPE = "chat_completion"

# System prompts (can be expanded later)
SYSTEM_PROMPTS = {
    "assistant": "You are an expert assistant!",
    "websearch_system_prompt": "You are a helpful search assistant.",
}

# Provider-specific defaults
PROVIDER_DEFAULTS = {
    "openai": {
        "temperature_max": 2.0,
        "supports_streaming": True,
        "supports_temperature": True,
    },
    "anthropic": {
        "temperature_max": 1.0,
        "supports_streaming": True,
        "supports_temperature": True,
    },
    "gemini": {
        "temperature_max": 2.0,
        "supports_streaming": True,
        "supports_temperature": True,
    },
    "perplexity": {
        "temperature_max": 2.0,
        "supports_streaming": True,
        "supports_temperature": True,
        "supports_citations": True,
    },
    "deepseek": {
        "temperature_max": 2.0,
        "supports_streaming": True,
        "supports_temperature": True,
    },
    "xai": {
        "temperature_max": 2.0,
        "supports_streaming": True,
        "supports_temperature": True,
    },
    "groq": {
        "temperature_max": 2.0,
        "supports_streaming": True,
        "supports_temperature": True,
    },
}

__all__ = [
    "DEFAULT_TEMPERATURE",
    "DEFAULT_TEMPERATURE_MIN",
    "DEFAULT_TEMPERATURE_MAX",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_FILE_ATTACHED_MESSAGE_LIMIT",
    "DEFAULT_REASONING_EFFORT_VALUES",
    "DEFAULT_REASONING_EFFORT_INDEX",
    "DEFAULT_API_TYPE",
    "SYSTEM_PROMPTS",
    "PROVIDER_DEFAULTS",
]
