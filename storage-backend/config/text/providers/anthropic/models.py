"""Anthropic model definitions for the registry."""

from __future__ import annotations

from config.batch.defaults import (
    BATCH_MAX_FILE_SIZE_MB_ANTHROPIC,
    BATCH_MAX_REQUESTS_ANTHROPIC,
)
from core.providers.registry.model_config import ModelConfig

BATCH_CONFIG = {
    "supports_batch_api": True,
    "batch_max_requests": BATCH_MAX_REQUESTS_ANTHROPIC,
    "batch_max_file_size_mb": BATCH_MAX_FILE_SIZE_MB_ANTHROPIC,
}

ANTHROPIC_MODELS: dict[str, ModelConfig] = {
    "claude-sonnet": ModelConfig(
        model_name="claude-sonnet-4-5",
        provider_name="anthropic",
        support_image_input=True,
        temperature_max=1.0,
        supports_reasoning_effort=True,
        reasoning_model_counterpart="claude-opus",
        reasoning_effort_values=[2048, 8000, 16000],
        **BATCH_CONFIG,
    ),
    "claude-opus": ModelConfig(
        model_name="claude-opus-4-6",
        provider_name="anthropic",
        is_reasoning_model=True,
        support_image_input=True,
        temperature_max=1.0,
        supports_reasoning_effort=True,
        reasoning_effort_values=[2048, 8000, 16000],
        **BATCH_CONFIG,
    ),
    "claude-haiku": ModelConfig(
        model_name="claude-haiku-4-5",
        provider_name="anthropic",
        support_image_input=True,
        temperature_max=1.0,
        **BATCH_CONFIG,
    ),
}
