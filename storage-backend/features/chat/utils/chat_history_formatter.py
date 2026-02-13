"""Utilities for extracting and formatting chat history payloads."""

from __future__ import annotations

import logging
from typing import Any, Optional

from .content_processor import process_message_content

logger = logging.getLogger(__name__)


def extract_and_format_chat_history(
    *,
    user_input: Optional[dict[str, Any]] = None,
    system_prompt: Optional[str] = None,
    provider_name: str = "openai",
    model_name: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Return a provider-ready messages list including prior chat history.

    Args:
        user_input: Original user input payload that may contain chat history.
        system_prompt: Optional system prompt to prepend/append when required.
        provider_name: Provider identifier used for format-specific adjustments.
        model_name: Optional model identifier for provider-specific formatting.
    """

    payload = user_input or {}
    chat_history = payload.get("chat_history") or []
    current_prompt = payload.get("prompt")

    history_messages: list[dict[str, Any]] = []
    if isinstance(chat_history, list):
        for item in chat_history:
            if isinstance(item, dict):
                history_messages.append(dict(item))
            else:
                logger.debug("Skipping non-dict chat history item: %r", item)

    messages: list[dict[str, Any]] = []

    # Insert system prompt when the provider expects it inside the messages array.
    if system_prompt:
        provider_key = provider_name.lower()
        if provider_key in {"anthropic", "gemini"}:
            logger.debug(
                "System prompt handled separately for provider %s; skipping messages insert",
                provider_key,
            )
        elif provider_key in {"deepseek", "perplexity"}:
            messages.append({"role": "system", "content": system_prompt})
        else:
            messages.append({"role": "system", "content": system_prompt})

    if history_messages:
        messages.extend(history_messages)

    if current_prompt:
        if isinstance(current_prompt, dict):
            messages.append(current_prompt)
        elif isinstance(current_prompt, list):
            processed_content = process_message_content(
                content=current_prompt,
                provider_name=provider_name,
                model_name=model_name or "",
            )
            messages.append({"role": "user", "content": processed_content})
        else:
            messages.append({"role": "user", "content": current_prompt})

    logger.debug(
        "Formatted chat history: %s" % str(history_messages)[:200]
    )

    return messages


def get_provider_name_from_model(model_name: str) -> str:
    """Derive a provider identifier based on the model name."""

    model_lower = model_name.lower()
    if model_lower.startswith("claude") or model_lower.startswith("anthropic"):
        return "anthropic"
    if model_lower.startswith("gpt-") or model_lower.startswith("o3-") or model_lower.startswith("o4-"):
        return "openai"
    if model_lower.startswith("grok"):
        return "xai"
    if model_lower.startswith("gemini"):
        return "gemini"
    if model_lower.startswith("deepseek"):
        return "deepseek"
    if model_lower.startswith("sonar") or model_lower.startswith("perplexity"):
        return "perplexity"
    if model_lower.startswith("llama") or model_lower.startswith("mixtral"):
        return "groq"
    return "openai"


__all__ = ["extract_and_format_chat_history", "get_provider_name_from_model"]
