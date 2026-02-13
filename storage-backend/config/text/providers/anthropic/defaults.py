"""Anthropic Claude default settings."""

# Model defaults
DEFAULT_MODEL = "claude-sonnet-4-5"

# Generation defaults
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 4096

# Thinking configuration
DEFAULT_THINKING_ENABLED = False
DEFAULT_THINKING_BUDGET = 10_000  # tokens

__all__ = [
    "DEFAULT_MODEL",
    "DEFAULT_TEMPERATURE",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_THINKING_ENABLED",
    "DEFAULT_THINKING_BUDGET",
]
