"""Configuration helpers for the deep research workflow."""

from __future__ import annotations

from typing import Any, Dict, Optional

import logging

logger = logging.getLogger(__name__)

DEEP_RESEARCH_DEFAULTS: Dict[str, Any] = {
    "default_model": "perplexity",
    "supported_models": ["perplexity"],
    "deep_research_model": "perplexity",
    "deep_research_reasoning_effort": 1,
    "optimization_temperature": 0.2,
    "optimization_max_tokens": 800,
    "research_temperature": 0.2,
    "research_max_tokens": 2048,
    "enable_prompt_optimization": True,
    "enable_citation_storage": True,
    "session_name_prefix": "Deep Research",
}


def validate_deep_research_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    """Validate settings required for the deep research workflow."""

    text_settings = settings.get("text", {}) if isinstance(settings, dict) else {}

    if not text_settings.get("deep_research_enabled", False):
        raise ValueError("Deep research is not enabled in settings")

    research_model = text_settings.get(
        "deep_research_model", DEEP_RESEARCH_DEFAULTS["default_model"]
    )

    if research_model not in DEEP_RESEARCH_DEFAULTS["supported_models"]:
        logger.warning(
            "Unsupported deep research model '%s', falling back to '%s'",
            research_model,
            DEEP_RESEARCH_DEFAULTS["default_model"],
        )
        research_model = DEEP_RESEARCH_DEFAULTS["default_model"]

    primary_model = text_settings.get("model")
    if not primary_model:
        raise ValueError("No primary model configured for deep research")

    normalised_settings = dict(settings)
    normalised_text_settings = dict(text_settings)
    normalised_text_settings["deep_research_model"] = research_model
    normalised_settings["text"] = normalised_text_settings
    return normalised_settings


def get_deep_research_config(
    setting_key: str, user_settings: Optional[Dict[str, Any]] = None
) -> Any:
    """Return configuration values honouring user overrides when available."""

    if user_settings:
        text_settings = user_settings.get("text", {})
        if setting_key in text_settings:
            return text_settings[setting_key]

        if (
            setting_key == "deep_research_reasoning_effort"
            and "perplexity_search_context_size" in text_settings
        ):
            return text_settings["perplexity_search_context_size"]

    return DEEP_RESEARCH_DEFAULTS.get(setting_key)


__all__ = [
    "DEEP_RESEARCH_DEFAULTS",
    "validate_deep_research_settings",
    "get_deep_research_config",
]
