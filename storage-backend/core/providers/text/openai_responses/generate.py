"""Non-streaming helpers for the OpenAI Responses API."""

from __future__ import annotations

import logging
from typing import Any

from core.exceptions import ProviderError, RateLimitError
from core.providers.registry.model_config import ModelConfig
from core.providers.text.responses_utils import (
    build_responses_params,
    extract_fallback_output_text,
    extract_text_from_output,
)
from core.providers.text.utils import log_responses_tool_calls
from core.pydantic_schemas import ProviderResponse

logger = logging.getLogger(__name__)


async def generate_responses_api(
    *,
    client: Any,
    model_config: ModelConfig | None,
    messages: list[dict[str, Any]],
    model: str,
    temperature: float,
    max_tokens: int,
    enable_reasoning: bool,
    **kwargs: Any,
) -> ProviderResponse:
    """Generate a response using the OpenAI Responses API."""

    params = build_responses_params(
        model=model,
        messages=messages,
        model_config=model_config,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=False,
        extra_kwargs=kwargs,
        enable_reasoning=enable_reasoning,
    )

    logger.debug(
        "OpenAI Responses API call: model=%s, input_items=%d, params=%s",
        model,
        len(params.get("input", [])),
        {
            "temperature": params.get("temperature"),
            "max_output_tokens": params.get("max_output_tokens"),
            "reasoning": params.get("reasoning"),
            "instructions": (params.get("instructions") or "none")[:50]
            if params.get("instructions")
            else "none",
        },
    )

    try:
        response = await client.responses.create(**params)
    except Exception as exc:  # pragma: no cover - handled below
        error_msg = str(exc)
        if "rate limit" in error_msg.lower():
            logger.warning("OpenAI rate limit hit: %s", exc)
            raise RateLimitError(f"OpenAI rate limit: {error_msg}", retry_after=60) from exc

        logger.error("OpenAI Responses API error: %s", exc)
        raise ProviderError(
            f"OpenAI Responses API error: {error_msg}",
            provider="openai",
            original_error=exc,
        ) from exc

    output = getattr(response, "output", None)
    log_responses_tool_calls(output, source="response", logger=logger)

    text, reasoning = extract_text_from_output(output)
    if not text:
        text = extract_fallback_output_text(response)

    metadata = {
        "finish_reason": getattr(response, "finish_reason", None),
        "usage": getattr(response, "usage", None),
    }

    return ProviderResponse(
        text=text,
        model=model,
        provider="openai",
        reasoning=reasoning,
        metadata=metadata,
    )


__all__ = ["generate_responses_api"]
