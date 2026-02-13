"""Non-streaming provider interactions for chat responses."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from core.exceptions import ProviderError, ValidationError
from core.pydantic_schemas import ProviderResponse

from features.chat.utils.prompt_utils import PromptInput, prompt_preview
from features.chat.utils.chat_history_formatter import (
    extract_and_format_chat_history,
    get_provider_name_from_model,
)
from features.chat.utils.reasoning_config import get_reasoning_config

from .context import resolve_prompt_and_provider

logger = logging.getLogger(__name__)


async def generate_response(
    *,
    prompt: PromptInput,
    settings: Dict[str, Any],
    customer_id: int,
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
    user_input: Optional[Dict[str, Any]] = None,
) -> ProviderResponse:
    """Request a full response from the configured provider without streaming."""

    context, provider, resolved_model, temperature, max_tokens = (
        resolve_prompt_and_provider(
            prompt=prompt,
            settings=settings,
            customer_id=customer_id,
            model=model,
        )
    )

    logger.info(
        "Generating response for customer %s using model %s", customer_id, resolved_model
    )
    logger.debug(
        "Prompt preview for customer %s (non-streaming): '%s'",
        customer_id,
        prompt_preview(prompt),
    )

    provider_name = get_provider_name_from_model(resolved_model)

    enable_reasoning, reasoning_value = get_reasoning_config(
        settings=settings.get("text", {}) if isinstance(settings, dict) else {},
        model_config=provider.get_model_config()
        if hasattr(provider, "get_model_config")
        else None,
    )

    logger.debug(
        "Reasoning config for customer %s: enabled=%s value=%s",
        customer_id,
        enable_reasoning,
        reasoning_value,
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
        base_message: dict[str, Any] = {"role": "user", "content": context.text_prompt}
        messages = [base_message]
        if system_prompt and provider_name != "anthropic":
            messages.insert(0, {"role": "system", "content": system_prompt})

    logger.debug(
        "Dispatching non-streaming request with %d messages (provider=%s)",
        len(messages),
        provider_name,
    )

    generate_kwargs: Dict[str, Any] = {
        "prompt": context.text_prompt,
        "model": resolved_model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "system_prompt": system_prompt,
        "messages": messages,
    }

    logger.debug(
        "Provider generate_kwargs keys: %s",
        list(generate_kwargs.keys()),
    )

    if enable_reasoning:
        generate_kwargs["enable_reasoning"] = True
        if reasoning_value is not None:
            generate_kwargs["reasoning_value"] = reasoning_value

    tool_settings = (
        settings.get("text", {}).get("tools")
        if isinstance(settings, dict)
        and isinstance(settings.get("text"), dict)
        else {}
    )
    if isinstance(tool_settings, dict) and tool_settings:
        generate_kwargs["tool_settings"] = tool_settings

    try:
        response = await provider.generate(**generate_kwargs)
        logger.info(
            "Non-streaming response generated (customer=%s, provider=%s, chars=%s)",
            customer_id,
            provider.__class__.__name__,
            len(response.text or ""),
        )
        return response
    except ProviderError:
        raise
    except ValidationError:
        raise
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Unexpected error in generate_response: %s", exc)
        raise ProviderError(f"Generation failed: {exc}") from exc


__all__ = ["generate_response"]
