"""Gemini model definitions for the registry."""

from __future__ import annotations

from config.batch.defaults import (
    BATCH_MAX_FILE_SIZE_MB_GEMINI,
    BATCH_MAX_REQUESTS_GEMINI,
)
from core.providers.registry.model_config import ModelConfig

BATCH_CONFIG = {
    "supports_batch_api": True,
    "batch_max_requests": BATCH_MAX_REQUESTS_GEMINI,
    "batch_max_file_size_mb": BATCH_MAX_FILE_SIZE_MB_GEMINI,
}

GEMINI_MODELS: dict[str, ModelConfig] = {
    "gemini-3-pro-preview": ModelConfig(
        model_name="gemini-3-pro-preview",
        provider_name="gemini",
        is_reasoning_model=True,
        support_image_input=True,
        support_audio_input=True,
        supports_reasoning_effort=True,
        reasoning_effort_values=[2048, 8000, 16000],
        **BATCH_CONFIG,
    ),
    "gemini-pro": ModelConfig(
        model_name="gemini-2.5-pro",
        provider_name="gemini",
        is_reasoning_model=True,
        support_image_input=True,
        support_audio_input=True,
        supports_reasoning_effort=True,
        reasoning_effort_values=[2048, 8000, 16000],
        **BATCH_CONFIG,
    ),
    "gemini-flash": ModelConfig(
        model_name="gemini-3-flash-preview",
        provider_name="gemini",
        is_reasoning_model=True,
        support_image_input=True,
        support_audio_input=True,
        supports_reasoning_effort=True,
        reasoning_effort_values=[2048, 8000, 16000],
        **BATCH_CONFIG,
    ),
}
