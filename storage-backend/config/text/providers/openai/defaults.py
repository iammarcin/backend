"""OpenAI text generation default settings."""

import os

# Model defaults
DEFAULT_MODEL = "gpt-5-nano"

# Generation defaults
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 4096

# Tool configuration
VERBOSE_TOOL_LOGGING = os.getenv("OPENAI_VERBOSE_TOOL_LOGGING", "false").lower() == "true"

__all__ = [
    "DEFAULT_MODEL",
    "DEFAULT_TEMPERATURE",
    "DEFAULT_MAX_TOKENS",
    "VERBOSE_TOOL_LOGGING",
]
