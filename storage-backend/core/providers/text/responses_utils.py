"""Utility functions for OpenAI Responses API operations.

This module contains helper functions for building parameters and extracting
data from OpenAI Responses API payloads, keeping the main API interaction
logic clean and focused.
"""

from __future__ import annotations

import logging
from typing import Any

from core.providers.registry.model_config import ModelConfig
from core.providers.text.utils import convert_to_responses_format

logger = logging.getLogger(__name__)


def build_responses_params(
    *,
    model: str,
    messages: list[dict[str, Any]],
    model_config: ModelConfig | None,
    temperature: float,
    max_tokens: int,
    stream: bool,
    extra_kwargs: dict[str, Any],
    enable_reasoning: bool,
    tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the base parameter payload for Responses API calls."""
    responses_input, system_instruction = convert_to_responses_format(messages)

    # Get builtin tool config from extra_kwargs if available
    builtin_tool_config = extra_kwargs.get("builtin_tool_config")

    default_tools = []
    # Only add web_search if not disabled by profile
    if builtin_tool_config is None or builtin_tool_config.get("web_search", True):
        default_tools.append({"type": "web_search"})

    # Only add code_interpreter if not disabled by profile and supported
    if (model_config is None or model_config.supports_code_interpreter) and (
        builtin_tool_config is None or builtin_tool_config.get("code_interpreter", True)
    ):
        default_tools.append({"type": "code_interpreter", "container": {"type": "auto"}})

    final_tools: list[dict[str, Any]] = []
    if tools:
        for tool in tools:
            if tool.get("type") == "function" and "function" in tool:
                func = tool["function"]
                converted = {
                    "type": "function",
                    "name": func["name"],
                    "description": func.get("description", ""),
                    "parameters": func.get("parameters", {}),
                }
                final_tools.append(converted)
                logger.debug(
                    "Converted tool: %s - %s",
                    func["name"],
                    func.get("description", "")[:100],
                )
            else:
                final_tools.append(tool)

        final_tools.extend(default_tools)
        logger.info(
            "Total tools: %d (%d custom + %d default)",
            len(final_tools),
            len(tools),
            len(default_tools),
        )
    else:
        final_tools = list(default_tools)
        logger.debug("Using default tools only")

    params: dict[str, Any] = {
        "model": model,
        "input": responses_input,
        "tools": final_tools,
        "stream": stream,
    }

    if system_instruction:
        params["instructions"] = system_instruction

    if model_config and model_config.supports_temperature:
        params["temperature"] = temperature

    reasoning_effort = extra_kwargs.pop("reasoning_effort", None)

    if enable_reasoning and model_config and model_config.supports_reasoning_effort:
        # Use model-specific effort values with fallback to "low"
        # For models like gpt-5-pro that only support "high", this ensures
        # we use the correct default from the model config
        effort_values = model_config.reasoning_effort_values or ["low", "medium", "high"]
        default_effort = effort_values[0] if effort_values else "low"

        resolved_effort = reasoning_effort or default_effort

        # Build reasoning object with effort and summary
        # summary is required to actually receive reasoning summaries from the API
        params["reasoning"] = {
            "effort": resolved_effort,
            "summary": "auto",
        }
        logger.debug("Responses API reasoning enabled: effort=%s summary=detailed", resolved_effort)
    elif reasoning_effort:
        logger.debug(
            "Reasoning effort %s was provided but reasoning is disabled; value ignored",
            reasoning_effort,
        )

    if max_tokens:
        params["max_output_tokens"] = max_tokens

    logger.info(
        "Responses API request: model=%s, tools=%d, messages=%d",
        model,
        len(final_tools),
        len(responses_input),
    )

    return params


def extract_text_from_output(output: Any) -> tuple[str, Any]:
    """Extract text and reasoning content from a Responses API payload."""
    text_parts: list[str] = []
    reasoning = None

    if output:
        for item in output:
            item_type = getattr(item, "type", None) or (
                item.get("type") if isinstance(item, dict) else None
            )

            if item_type in {"text", "output_text"}:
                text = getattr(item, "text", None)
                if text:
                    text_parts.append(text)
                    continue

                content = getattr(item, "content", None)
                if isinstance(content, list):
                    for content_item in content:
                        text_piece = getattr(content_item, "text", None) or (
                            content_item.get("text")
                            if isinstance(content_item, dict)
                            else None
                        )
                        if text_piece:
                            text_parts.append(text_piece)
                continue

            if item_type == "message":
                content = getattr(item, "content", None) or (
                    item.get("content") if isinstance(item, dict) else None
                )
                if isinstance(content, list):
                    for content_item in content:
                        content_type = getattr(content_item, "type", None) or (
                            content_item.get("type")
                            if isinstance(content_item, dict)
                            else None
                        )
                        if content_type in {"text", "output_text"}:
                            text_piece = getattr(content_item, "text", None) or (
                                content_item.get("text")
                                if isinstance(content_item, dict)
                                else None
                            )
                            if text_piece:
                                text_parts.append(text_piece)
                        elif content_type in {"reasoning", "thinking"} and reasoning is None:
                            reasoning = getattr(content_item, "content", None) or (
                                getattr(content_item, "text", None)
                                if not isinstance(content_item, dict)
                                else content_item.get("content")
                                or content_item.get("text")
                            )
                continue

            if item_type in {"reasoning", "thinking"} and reasoning is None:
                reasoning = getattr(item, "content", None) or getattr(item, "text", None)

    return "".join(text_parts), reasoning


def extract_fallback_output_text(response: Any) -> str:
    """Extract output_text as fallback when output chunks are not available."""
    output_text = getattr(response, "output_text", None)
    if output_text:
        if isinstance(output_text, (list, tuple)):
            return "".join(str(part) for part in output_text if part)
        return str(output_text)
    return ""


__all__ = [
    "build_responses_params",
    "extract_text_from_output",
    "extract_fallback_output_text",
]
