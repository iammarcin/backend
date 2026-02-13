"""Helper utilities for configuring Gemini text generation requests."""

from __future__ import annotations

from copy import deepcopy
import logging
from typing import Any, Iterable, Optional

from google.genai import types  # type: ignore

from config.text.providers.gemini import defaults as gemini_defaults
from core.providers.text.utils import build_gemini_tools

logger = logging.getLogger("core.providers.text.gemini")

_DEFAULT_TOOL_SETTINGS: dict[str, Any] = gemini_defaults.DEFAULT_TOOL_SETTINGS


def has_custom_function_declarations(tools: Any) -> bool:
    """Return ``True`` when Gemini tool payloads contain custom functions."""

    if not tools:
        return False

    if isinstance(tools, dict):
        if "function_declarations" in tools:
            return has_custom_function_declarations(tools.get("function_declarations"))
        if "functions" in tools:
            return has_custom_function_declarations(tools.get("functions"))
        candidate_entries: Iterable[Any] = (tools,)
    elif isinstance(tools, (list, tuple, set)):
        candidate_entries = tools
    else:
        return False

    for entry in candidate_entries:
        if isinstance(entry, dict):
            declarations = entry.get("function_declarations")
            if isinstance(declarations, (list, tuple, set)):
                if any(declarations):
                    return True

            name = entry.get("name")
            if isinstance(name, str) and name.strip():
                return True

        if hasattr(entry, "function_declarations"):
            if getattr(entry, "function_declarations"):
                return True

    return False


def _requires_thinking_mode(model_name: str) -> bool:
    """Return ``True`` when the model mandates thinking mode."""

    return "pro" in model_name.lower()


def build_generation_config(
    *,
    model_name: str,
    temperature: float,
    max_tokens: int,
    system_prompt: Optional[str],
    enable_reasoning: bool,
    reasoning_value: Optional[int],
) -> types.GenerateContentConfig:
    """Create a ``GenerateContentConfig`` with reasoning defaults applied."""

    config = types.GenerateContentConfig(max_output_tokens=max_tokens)
    config.temperature = temperature
    if system_prompt:
        config.system_instruction = system_prompt

    if enable_reasoning:
        thinking_budget = 2048
        if reasoning_value is not None:
            if isinstance(reasoning_value, int):
                thinking_budget = reasoning_value
            else:
                logger.warning(
                    "Gemini reasoning_value %r is not int; defaulting to 2048",
                    reasoning_value,
                )
        config.thinking_config = types.ThinkingConfig(
            thinking_budget=thinking_budget,
            include_thoughts=True,
        )
        logger.debug("Gemini thinking enabled with budget %s", thinking_budget)
        return config

    if _requires_thinking_mode(model_name):
        config.thinking_config = types.ThinkingConfig(
            include_thoughts=False,
            thinking_budget=-1,
        )
        logger.debug("Gemini Pro: using dynamic thinking (budget=-1)")
    else:
        config.thinking_config = types.ThinkingConfig(
            include_thoughts=False,
            thinking_budget=0,
        )
        logger.debug("Gemini Flash: thinking disabled (budget=0)")

    return config


def prepare_tool_settings(raw_settings: Any) -> dict[str, Any]:
    """Return merged tool settings with defaults that keep tools available.

    Tool priority (highest to lowest):
    1. API mixing limitation (if custom functions present)
    2. Explicit user settings (raw_settings.tools)
    3. Provider defaults (_DEFAULT_TOOL_SETTINGS)
    """

    settings: dict[str, Any] = deepcopy(_DEFAULT_TOOL_SETTINGS)

    if not isinstance(raw_settings, dict):
        return settings

    # Merge explicit settings (highest priority after mixing)
    for key, value in raw_settings.items():
        if key == "functions" and isinstance(value, list):
            existing = list(settings.get("functions", []))
            existing.extend(
                [entry for entry in value if isinstance(entry, dict)]
            )
            settings["functions"] = existing
            continue

        if (
            key in settings
            and isinstance(settings[key], dict)
            and isinstance(value, dict)
        ):
            merged = dict(settings[key])
            merged.update(value)
            settings[key] = merged
        else:
            settings[key] = value

    # Check for custom function declarations (API mixing limitation)
    if has_custom_function_declarations(settings.get("functions")):
        logger.info(
            "Gemini: Custom functions detected; "
            "disabling native tools (google_search, code_execution) due to API limitation"
        )
        search_settings = settings.get("google_search")
        if isinstance(search_settings, dict):
            disabled_settings = dict(search_settings)
            disabled_settings["enabled"] = False
        else:
            disabled_settings = {"enabled": False}
        settings["google_search"] = disabled_settings
        settings["code_execution"] = False
    else:
        logger.debug(
            "Gemini: No custom functions detected; native tools remain enabled"
        )

    return settings


def apply_tools_to_config(
    *,
    config: types.GenerateContentConfig,
    tool_settings: dict[str, Any],
    context: str,
) -> None:
    """Attach configured tools to ``config`` and emit diagnostic logs."""

    logger.debug("Gemini %s tool_settings: %s", context, tool_settings)
    tools, tool_log_payload = build_gemini_tools(tool_settings)
    if tools:
        config.tools = tools
        logger.info("Gemini tools enabled (%s): %s", context, tool_log_payload)
    else:
        logger.debug("Gemini %s: no tools configured", context)


__all__ = [
    "apply_tools_to_config",
    "build_generation_config",
    "has_custom_function_declarations",
    "prepare_tool_settings",
]
