"""Helper utilities for building xAI request parameters."""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from xai_sdk import chat
from xai_sdk import tools as xai_tools

from core.providers.base import BaseTextProvider


def resolve_model_alias(provider: BaseTextProvider, fallback: str | None) -> str:
    """Return the canonical model name from the registry when available."""

    model_config = provider.get_model_config() if hasattr(provider, "get_model_config") else None
    if model_config and model_config.model_name:
        return model_config.model_name
    if fallback:
        return fallback
    return "grok-4-latest"


def build_tool_payload(
    tool_settings: Mapping[str, Any] | None,
) -> tuple[Optional[Sequence[Any]], Optional[Any], Optional[bool]]:
    """Convert OpenAI-style tool settings into xAI SDK parameters."""

    if not isinstance(tool_settings, Mapping) or not tool_settings:
        return None, None, None

    functions = tool_settings.get("functions")
    tools: list[Any] = []
    if isinstance(functions, Sequence):
        for entry in functions:
            if not isinstance(entry, Mapping):
                continue
            name = entry.get("name") or entry.get("function", {}).get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            description = entry.get("description") or ""
            parameters = entry.get("parameters") or {"type": "object", "properties": {}}
            if not isinstance(parameters, Mapping):
                parameters = {"type": "object", "properties": {}}
            tools.append(
                chat.tool(
                    name=name,
                    description=str(description or ""),
                    parameters=dict(parameters),
                )
            )

    tool_choice_setting = tool_settings.get("tool_choice")
    tool_choice: Any = None
    if isinstance(tool_choice_setting, Mapping):
        choice_type = str(tool_choice_setting.get("type") or "").lower()
        if choice_type == "function":
            function_payload = tool_choice_setting.get("function")
            if isinstance(function_payload, Mapping):
                function_name = function_payload.get("name")
                if isinstance(function_name, str) and function_name.strip():
                    tool_choice = chat.required_tool(function_name)
        elif choice_type in {"auto", "none", "required"}:
            tool_choice = choice_type
    elif isinstance(tool_choice_setting, str) and tool_choice_setting:
        tool_choice = tool_choice_setting

    parallel_tool_calls = tool_settings.get("parallel_tool_calls")
    parallel_flag = bool(parallel_tool_calls) if parallel_tool_calls is not None else None

    return (tools or None, tool_choice, parallel_flag)


def filter_request_kwargs(kwargs: Mapping[str, Any]) -> dict[str, Any]:
    """Remove BetterAI-specific keys before forwarding to the SDK."""

    allowed = dict(kwargs)
    for key in ("system_prompt", "messages", "tool_settings", "manager", "settings"):
        allowed.pop(key, None)

    enable_reasoning = bool(allowed.pop("enable_reasoning", False))
    reasoning_value = allowed.pop("reasoning_value", None)
    existing_effort = allowed.pop("reasoning_effort", None)
    if enable_reasoning and reasoning_value:
        allowed["reasoning_effort"] = reasoning_value
    elif existing_effort:
        allowed["reasoning_effort"] = existing_effort

    return allowed


def ensure_default_server_side_tools(params: dict[str, Any]) -> None:
    """Ensure web search and X search tools are always available."""

    existing = list(params.get("tools") or [])
    has_web_search = any(getattr(tool, "HasField", lambda *_: False)("web_search") for tool in existing)
    has_x_search = any(getattr(tool, "HasField", lambda *_: False)("x_search") for tool in existing)

    if not has_web_search:
        existing.append(xai_tools.web_search(enable_image_understanding=True))
    if not has_x_search:
        existing.append(
            xai_tools.x_search(
                enable_image_understanding=True,
                enable_video_understanding=False,
            )
        )

    if existing:
        params["tools"] = existing


__all__ = [
    "build_tool_payload",
    "ensure_default_server_side_tools",
    "filter_request_kwargs",
    "resolve_model_alias",
]
