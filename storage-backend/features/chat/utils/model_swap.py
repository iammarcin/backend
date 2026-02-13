"""
Model Swap Utility

Provides helpers for swapping between text providers mid-request,
required for deep research workflow that uses multiple models.
"""
from __future__ import annotations

from typing import Any, Dict

import logging
from core.providers.base import BaseTextProvider
from core.providers.factory import get_text_provider

logger = logging.getLogger(__name__)


def get_provider_for_model(
    model_name: str,
    base_settings: Dict[str, Any],
    enable_reasoning: bool = False,
) -> BaseTextProvider:
    """Get a text provider instance for a specific model."""

    temp_settings = dict(base_settings)
    text_settings = dict(temp_settings.get("text", {}))
    text_settings["model"] = model_name
    text_settings["enable_reasoning"] = enable_reasoning
    temp_settings["text"] = text_settings

    provider = get_text_provider(temp_settings)
    logger.debug("Created provider for model: %s", model_name)
    return provider


def save_model_config(settings: Dict[str, Any]) -> Dict[str, Any]:
    """Save current model configuration from settings."""

    text_settings = settings.get("text", {}) if isinstance(settings, dict) else {}
    return {
        "model": text_settings.get("model"),
        "enable_reasoning": text_settings.get("enable_reasoning", False),
        "temperature": text_settings.get("temperature"),
        "max_tokens": text_settings.get("max_tokens"),
    }


def restore_model_config(settings: Dict[str, Any], saved_config: Dict[str, Any]) -> Dict[str, Any]:
    """Restore previously saved model configuration."""

    if not isinstance(settings, dict):
        return settings

    text_settings = dict(settings.get("text", {}))
    text_settings.update(saved_config)
    settings["text"] = text_settings
    return settings


__all__ = [
    "get_provider_for_model",
    "save_model_config",
    "restore_model_config",
]
