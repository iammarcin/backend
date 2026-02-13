"""Provider-specific batch API configuration."""

# OpenAI Batch API settings
OPENAI_BATCH_ENDPOINT = "/v1/chat/completions"
"""OpenAI batch endpoint for chat completions."""

OPENAI_BATCH_COMPLETION_WINDOW = "24h"
"""OpenAI batch completion window."""

# Anthropic Batch API settings
ANTHROPIC_BATCH_RESULT_EXPIRY_DAYS = 29
"""How long Anthropic batch results remain available."""

ANTHROPIC_BATCH_WORKSPACE_SCOPED = True
"""Whether Anthropic batches are scoped to workspace."""

# Gemini Batch API settings
GEMINI_BATCH_TARGET_TURNAROUND_HOURS = 24
"""Target turnaround time for Gemini batches (in hours)."""

GEMINI_BATCH_SLO_HOURS = 24
"""Gemini Batch API Service Level Objective (in hours)."""

# Cost savings (all providers)
BATCH_COST_DISCOUNT_PERCENTAGE = 50
"""Cost discount for batch vs real-time (all providers offer 50%)."""


__all__ = [
    "OPENAI_BATCH_ENDPOINT",
    "OPENAI_BATCH_COMPLETION_WINDOW",
    "ANTHROPIC_BATCH_RESULT_EXPIRY_DAYS",
    "ANTHROPIC_BATCH_WORKSPACE_SCOPED",
    "GEMINI_BATCH_TARGET_TURNAROUND_HOURS",
    "GEMINI_BATCH_SLO_HOURS",
    "BATCH_COST_DISCOUNT_PERCENTAGE",
]
