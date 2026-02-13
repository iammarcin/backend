"""Helpers for reasoning/thinking configuration mapping."""

from __future__ import annotations

import logging
from typing import Any, Optional, Tuple

from core.providers.registry import ModelConfig

logger = logging.getLogger(__name__)


def _coerce_effort_index(value: Any, *, default: int = 1) -> int:
    """Return a safe integer index for reasoning effort selections."""

    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        logger.debug("Invalid reasoning_effort value %r, falling back to %s", value, default)
        return default


def get_reasoning_config(
    *,
    settings: Optional[dict[str, Any]],
    model_config: Optional[ModelConfig],
) -> Tuple[bool, Any]:
    """Map unified reasoning settings to provider specific payload values.

    Parameters
    ----------
    settings:
        Frontend provided text settings. Expected to contain ``enable_reasoning``
        and ``reasoning_effort`` values.
    model_config:
        Registry metadata for the resolved model. Used to determine whether the
        model supports reasoning effort mappings and to look up the provider
        specific effort values.

    Returns
    -------
    tuple[bool, Any]
        ``(enabled, reasoning_value)`` where ``reasoning_value`` is provider
        specific (string for OpenAI, integer token budget for Anthropic/Gemini).
    """

    if not settings:
        return False, None

    enable_reasoning = bool(settings.get("enable_reasoning", False))
    if not enable_reasoning:
        return False, None

    if not model_config:
        logger.debug("Reasoning requested but no model configuration available")
        return False, None

    if not model_config.supports_reasoning_effort:
        logger.debug(
            "Model %s does not support reasoning effort overrides", model_config.model_name
        )
        return False, None

    effort_values = model_config.reasoning_effort_values or ["low", "medium", "high"]
    effort_index = _coerce_effort_index(settings.get("reasoning_effort", 1))

    if effort_index < 0 or effort_index >= len(effort_values):
        clamped_index = max(0, min(effort_index, len(effort_values) - 1))
        logger.warning(
            "Reasoning effort index %s out of range for %s (values=%s); clamped to %s",
            effort_index,
            model_config.model_name,
            effort_values,
            clamped_index,
        )
        effort_index = clamped_index

    reasoning_value = effort_values[effort_index]
    return True, reasoning_value


__all__ = ["get_reasoning_config"]
