"""Helpers for resolving system prompts settings."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

try:  # pragma: no cover - exercised indirectly via fallback in tests
    from itisai_brain.text import getTextPromptTemplate as _imported_get_text_prompt_template
except ModuleNotFoundError:  # pragma: no cover - fallback for local/unit tests
    _FALLBACK_PROMPTS: Dict[str, str] = {
        "assistant": (
            "You are a highly capable, thoughtful, and precise assistant."
            "Your goal is to deeply understand the user's intent, ask clarifying questions when needed, think step-by-step through complex problems, provide clear and accurate answers, and proactively anticipate helpful follow-up information."
            "Always prioritize being truthful, nuanced, insightful, and efficient, tailoring your responses specifically to the user's needs and preferences."
        ),
        "flowstudio_clarification": (
            "You are a creative consultant helping storyboard FlowStudio videos. "
            "Ask clarifying questions and Return ONLY valid JSON with your prompts "
            "and reasoning."
        ),
    }

    def _brain_get_text_prompt_template(name: str) -> Dict[str, str]:
        template = _FALLBACK_PROMPTS.get(name)
        if template is None and name.endswith("_ai_agent"):
            base_name = name[: -len("_ai_agent")]
            template = _FALLBACK_PROMPTS.get(base_name)
        return {"template": template or _FALLBACK_PROMPTS["assistant"]}

else:  # pragma: no cover
    def _brain_get_text_prompt_template(name: str) -> Any:
        return _imported_get_text_prompt_template(name)


def _extract_template(raw_template: Any) -> str:
    """Normalize templates returned by ``getTextPromptTemplate``."""

    if isinstance(raw_template, dict):
        value = raw_template.get("template", "")
        return value if isinstance(value, str) else str(value)
    if isinstance(raw_template, str):
        return raw_template
    if raw_template is None:
        return ""
    return str(raw_template)


def set_system_prompt(ai_character: str, ai_agent_enabled: bool = False) -> str:
    """Determine the system prompt for a given AI character configuration."""

    ai_character = (ai_character or "assistant").strip() or "assistant"

    if ai_agent_enabled:
        candidate = f"{ai_character}_ai_agent"
        candidate_template = _extract_template(_brain_get_text_prompt_template(candidate))
        base_template = _extract_template(_brain_get_text_prompt_template(ai_character))
        default_template = _extract_template(_brain_get_text_prompt_template("assistant"))

        if candidate_template and candidate_template != default_template:
            return candidate_template
        if base_template and base_template != default_template:
            return base_template
        return default_template

    return _extract_template(_brain_get_text_prompt_template(ai_character))


def resolve_system_prompt(settings: Dict[str, Any] | None) -> Optional[str]:
    """Resolve the system prompt string from request settings."""

    if not settings:
        logger.debug("No settings provided, using default 'assistant' character")
        return set_system_prompt("assistant")

    text_settings = settings.get("text") or {}
    ai_character = text_settings.get("ai_character") or "assistant"
    ai_agent_enabled = bool(text_settings.get("ai_agent_enabled"))

    system_prompt = set_system_prompt(str(ai_character), ai_agent_enabled)
    cleaned = system_prompt.strip()

    return cleaned or None


__all__ = ["resolve_system_prompt", "set_system_prompt"]
