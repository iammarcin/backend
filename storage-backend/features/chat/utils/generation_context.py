"""Helpers for resolving chat generation context."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from core.exceptions import ValidationError
from core.providers.base import BaseTextProvider
from core.providers.factory import get_text_provider

logger = logging.getLogger(__name__)


def resolve_generation_context(
    *,
    prompt_text: str,
    settings: Dict[str, Any],
    customer_id: int,
    model: Optional[str] = None,
) -> Tuple[BaseTextProvider, str, float, int]:
    """Validate input and resolve provider parameters."""

    if not prompt_text or not prompt_text.strip():
        raise ValidationError("Prompt cannot be empty", field="prompt")
    if customer_id <= 0:
        raise ValidationError("Invalid customer_id", field="customer_id")

    settings = settings or {}
    provider = get_text_provider(settings)
    model_config = provider.get_model_config()

    resolved_model = model or settings.get("text", {}).get("model", "gpt-4o-mini")
    if model_config:
        resolved_model = model_config.model_name

    temperature = float(settings.get("text", {}).get("temperature", 0.1))
    if model_config and model_config.supports_temperature:
        temperature = max(
            model_config.temperature_min,
            min(model_config.temperature_max, temperature),
        )
    elif model_config and not model_config.supports_temperature:
        temperature = 1.0

    max_tokens = int(settings.get("text", {}).get("max_tokens", 0) or 0)
    if model_config:
        max_tokens = max_tokens or model_config.max_tokens_default

    logger.info(
        "Resolved text provider %s for model %s (temperature=%s, max_tokens=%s)",
        provider.__class__.__name__,
        resolved_model,
        temperature,
        max_tokens,
    )

    return provider, resolved_model, float(temperature), int(max_tokens)


__all__ = ["resolve_generation_context"]
