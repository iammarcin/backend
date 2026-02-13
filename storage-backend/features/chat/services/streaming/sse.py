"""Server-Sent Event helpers for streaming chat responses."""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator, Dict, Optional

from core.exceptions import ProviderError, ValidationError

from features.chat.utils.prompt_utils import PromptInput, prompt_preview
from features.chat.utils.chat_history_formatter import (
    extract_and_format_chat_history,
    get_provider_name_from_model,
)

from .context import resolve_prompt_and_provider

logger = logging.getLogger(__name__)


async def stream_response_chunks(
    *,
    prompt: PromptInput,
    settings: Dict[str, Any],
    customer_id: int,
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
    user_input: Optional[Dict[str, Any]] = None,
) -> AsyncIterator[str]:
    """Yield response chunks for Server-Sent Events streaming."""

    context, provider, resolved_model, temperature, max_tokens = (
        resolve_prompt_and_provider(
            prompt=prompt,
            settings=settings,
            customer_id=customer_id,
            model=model,
        )
    )

    logger.info(
        "SSE streaming response for customer %s using model %s",
        customer_id,
        resolved_model,
    )
    logger.debug(
        "Prompt preview for customer %s (SSE): '%s'",
        customer_id,
        prompt_preview(prompt),
    )

    chunk_count = 0
    provider_name = getattr(provider, "provider_name", None) or get_provider_name_from_model(
        resolved_model
    )
    history_payload: Dict[str, Any] = {}
    if isinstance(user_input, dict):
        history_payload = dict(user_input)
    existing_prompt = history_payload.get("prompt")
    if isinstance(existing_prompt, list) or isinstance(existing_prompt, dict):
        history_payload["prompt"] = existing_prompt
    else:
        history_payload["prompt"] = context.text_prompt

    messages = extract_and_format_chat_history(
        user_input=history_payload,
        system_prompt=system_prompt if provider_name != "anthropic" else None,
        provider_name=provider_name,
        model_name=resolved_model,
    )
    if not messages:
        base_message = {"role": "user", "content": context.text_prompt}
        messages = [base_message]
        if system_prompt and provider_name != "anthropic":
            messages.insert(0, {"role": "system", "content": system_prompt})

    logger.debug(
        "SSE streaming with %d messages (provider=%s)", len(messages), provider_name
    )

    try:
        async for chunk in provider.stream(
            prompt=context.text_prompt,
            model=resolved_model,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
            messages=messages,
        ):
            chunk_count += 1
            if isinstance(chunk, (dict, list)):
                yield json.dumps(chunk)
            else:
                yield str(chunk)
        logger.info(
            "SSE streaming complete for customer %s (chunks_sent=%s)",
            customer_id,
            chunk_count,
        )
    except ProviderError:
        raise
    except ValidationError:
        raise
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Unexpected error in stream_response_chunks: %s", exc)
        raise ProviderError(f"Streaming failed: {exc}") from exc


__all__ = ["stream_response_chunks"]
