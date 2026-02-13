"""Audio configuration utilities."""

from __future__ import annotations

import logging
from typing import Optional

from config.audio.models import GEMINI_SPEECH_MODEL_ALIASES

logger = logging.getLogger(__name__)

FALLBACK_FLASH_MODEL = "gemini-2.5-flash"
FALLBACK_PRO_MODEL = "gemini-2.5-pro"


def get_gemini_default_model(production: bool) -> str:
    """Get the default Gemini model for the environment."""

    return FALLBACK_PRO_MODEL if production else FALLBACK_FLASH_MODEL


def normalise_gemini_model(candidate: Optional[str], production: bool = False) -> str:
    """Resolve Gemini model aliases to canonical model IDs."""

    fallback_model = FALLBACK_PRO_MODEL if production else FALLBACK_FLASH_MODEL

    if candidate is None:
        return fallback_model

    model_name = str(candidate).strip()
    if not model_name:
        return fallback_model

    alias = GEMINI_SPEECH_MODEL_ALIASES.get(model_name.lower())
    if alias:
        return alias

    if model_name.lower().startswith("gemini"):
        return model_name

    logger.debug(
        "Unsupported Gemini model '%s' supplied; using fallback '%s'",
        model_name,
        fallback_model,
    )
    return fallback_model


__all__ = ["get_gemini_default_model", "normalise_gemini_model"]
