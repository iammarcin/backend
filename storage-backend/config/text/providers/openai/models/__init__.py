"""Aggregated OpenAI model registry definitions."""

from __future__ import annotations

import logging
from typing import Dict

from core.providers.registry.model_config import ModelConfig

from .chat import CHAT_MODELS


logger = logging.getLogger(__name__)

OPENAI_MODELS: Dict[str, ModelConfig] = {
    **CHAT_MODELS,
}


def get_model_config(model: str) -> ModelConfig | None:
    """Return the configuration for a specific OpenAI model."""

    config = OPENAI_MODELS.get(model)

    if config and config.is_deprecated:
        replacement = config.replacement_model or "a newer model"
        logger.warning(
            "Model '%s' is deprecated. Use '%s' instead.",
            model,
            replacement,
        )

    return config


def list_models_by_category(model_category: str) -> list[str]:
    """Return all registered model identifiers for the given category."""

    return [
        model_id
        for model_id, config in OPENAI_MODELS.items()
        if config.category == model_category
    ]


def get_model_voices(model: str) -> tuple[str, ...] | None:
    """Return the supported voices for the given model, if any."""

    config = get_model_config(model)
    if config and config.voices:
        return config.voices
    return None


__all__ = [
    "OPENAI_MODELS",
    "get_model_config",
    "list_models_by_category",
    "get_model_voices",
]
