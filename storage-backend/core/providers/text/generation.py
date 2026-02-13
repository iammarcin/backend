"""OpenAI text generation logic (non-streaming).

This module contains the generate method implementation for the OpenAI text
provider, handling both standard chat completion and Responses API modes.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from core.exceptions import ProviderError, RateLimitError
from core.providers.registry.model_config import ModelConfig
from core.pydantic_schemas import ProviderResponse

from .openai_responses import generate_responses_api

logger = logging.getLogger(__name__)


async def generate_text(
    *,
    client: Any,
    model_config: ModelConfig | None,
    prompt: str,
    model: str,
    temperature: float,
    max_tokens: int,
    system_prompt: Optional[str],
    messages: Optional[list[dict[str, Any]]],
    enable_reasoning: bool,
    reasoning_value: Optional[str],
    is_reasoning_model: bool,
    uses_responses_api: bool,
    **kwargs: Any,
) -> ProviderResponse:
    """Generate a complete response (non-streaming)."""

    if (not prompt or not prompt.strip()) and not messages:
        raise ProviderError(
            "OpenAI prompt cannot be empty when no message history is provided",
            provider="openai",
        )

    final_messages = list(messages) if messages is not None else []
    if not final_messages:
        if system_prompt and not is_reasoning_model:
            final_messages.append({"role": "system", "content": system_prompt})
        final_messages.append({"role": "user", "content": prompt})

    resolved_reasoning_value: Optional[str] = reasoning_value or kwargs.get(
        "reasoning_effort"
    )

    if uses_responses_api:
        extra_kwargs = dict(kwargs)
        if enable_reasoning and resolved_reasoning_value:
            extra_kwargs["reasoning_effort"] = resolved_reasoning_value
        return await generate_responses_api(
            client=client,
            model_config=model_config,
            messages=final_messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            enable_reasoning=enable_reasoning,
            **extra_kwargs,
        )

    params: dict[str, Any] = {
        "model": model,
        "messages": final_messages,
        **kwargs,
    }

    if is_reasoning_model:
        params["max_completion_tokens"] = max_tokens
        params["temperature"] = 1.0
        if enable_reasoning and resolved_reasoning_value:
            params["reasoning_effort"] = resolved_reasoning_value
            logger.debug("OpenAI reasoning effort set to %s", resolved_reasoning_value)
    else:
        params["temperature"] = temperature
        params["max_tokens"] = max_tokens

    api_type = model_config.api_type if model_config else "chat_completion"
    logger.debug(
        "OpenAI API call: model=%s, api_type=%s, messages_count=%d, params=%s",
        model,
        api_type,
        len(params.get("messages", [])),
        {
            "temperature": params.get("temperature"),
            "max_tokens": params.get("max_tokens"),
            "max_completion_tokens": params.get("max_completion_tokens"),
            "reasoning_effort": params.get("reasoning_effort"),
        },
    )

    try:
        response = await client.chat.completions.create(**params)
    except Exception as exc:  # pragma: no cover - handled below
        error_msg = str(exc)
        if "rate limit" in error_msg.lower():
            logger.warning("OpenAI rate limit hit: %s", exc)
            raise RateLimitError(
                f"OpenAI rate limit: {error_msg}", retry_after=60
            ) from exc

        logger.error("OpenAI generate error: %s", exc)
        raise ProviderError(
            f"OpenAI API error: {error_msg}",
            provider="openai",
            original_error=exc,
        ) from exc

    message = response.choices[0].message
    text = getattr(message, "content", "")
    reasoning = getattr(message, "reasoning_content", None)

    metadata = {
        "finish_reason": getattr(response.choices[0], "finish_reason", None),
        "usage": response.usage.model_dump()
        if getattr(response, "usage", None)
        else None,
    }

    return ProviderResponse(
        text=text,
        model=model,
        provider="openai",
        reasoning=reasoning,
        metadata=metadata,
    )


__all__ = ["generate_text"]
