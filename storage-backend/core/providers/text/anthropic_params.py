"""Shared helpers for Anthropic provider parameter construction."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from config.text.providers.anthropic import defaults as anthropic_defaults

logger = logging.getLogger(__name__)


def prepare_messages(prompt: str, messages: Optional[List[dict[str, Any]]]) -> List[dict[str, Any]]:
    if messages is not None:
        return messages
    return [{"role": "user", "content": prompt}]


def build_api_params(
    *,
    model: Optional[str],
    messages: List[dict[str, Any]],
    max_tokens: int,
    temperature: float,
    system_prompt: Optional[str],
    enable_reasoning: bool,
    reasoning_value: Optional[int],
    tools: Optional[list[dict[str, Any]]] = None,
    extra_kwargs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    params: Dict[str, Any] = {
        "model": model or anthropic_defaults.DEFAULT_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
    }

    if tools is not None:
        params["tools"] = tools

    if system_prompt:
        params["system"] = system_prompt

    _apply_reasoning_config(
        params=params,
        enable_reasoning=enable_reasoning,
        reasoning_value=reasoning_value,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    if extra_kwargs:
        for key, value in extra_kwargs.items():
            if key not in params:
                params[key] = value

    return params


def _apply_reasoning_config(
    *,
    params: Dict[str, Any],
    enable_reasoning: bool,
    reasoning_value: Optional[int],
    temperature: float,
    max_tokens: int,
) -> None:
    if enable_reasoning and reasoning_value:
        budget_tokens = reasoning_value if isinstance(reasoning_value, int) else None
        if budget_tokens is None:
            logger.warning(
                "Anthropic reasoning_value %r is not int; defaulting to 4096",
                reasoning_value,
            )
            budget_tokens = 4096
        if budget_tokens < 1024:
            logger.warning(
                "Anthropic thinking budget %s below minimum; clamping to 1024",
                budget_tokens,
            )
            budget_tokens = 1024
        params["thinking"] = {"type": "enabled", "budget_tokens": budget_tokens}
        params["temperature"] = 1.0
        params["max_tokens"] = budget_tokens + max_tokens
        logger.debug(
            "Anthropic thinking enabled: budget=%s total_max_tokens=%s",
            budget_tokens,
            params["max_tokens"],
        )
    else:
        params["temperature"] = temperature


__all__ = ["build_api_params", "prepare_messages"]
