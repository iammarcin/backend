"""Batch operations for OpenAI provider."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from core.exceptions import ValidationError
from core.pydantic_schemas import ProviderResponse

logger = logging.getLogger(__name__)


def _extract_text(content: Any) -> str:
    """Extract text content from OpenAI response."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks = []
        for part in content:
            if isinstance(part, dict):
                chunks.append(part.get("text") or "")
            else:
                chunks.append(str(part))
        return "".join(chunks)
    return ""


async def process_openai_batch_response(
    provider_instance: Any,
    requests: List[Dict[str, Any]],
    results: List[Dict[str, Any]],
) -> List[ProviderResponse]:
    """Process OpenAI batch API results into ProviderResponse objects.

    Args:
        provider_instance: The OpenAI provider instance.
        requests: Original batch requests.
        results: Raw results from OpenAI batch API.

    Returns:
        List of ProviderResponse objects in request order.
    """
    default_model = provider_instance._model_config.model_name if provider_instance._model_config else "gpt-4o-mini"
    response_map: Dict[str, ProviderResponse] = {}

    for result in results:
        custom_id = result.get("custom_id")
        if not custom_id:
            continue

        original_request = result.get("original_request", {})
        model_name = original_request.get("model") or default_model

        if result.get("error"):
            error_payload = result["error"]
            response_map[custom_id] = ProviderResponse(
                text="",
                model=model_name,
                provider="openai",
                metadata={
                    "custom_id": custom_id,
                    "error": error_payload.get("message"),
                    "error_type": error_payload.get("type"),
                },
            )
            continue

        response_payload = result.get("response") or {}
        body = response_payload.get("body") or {}
        choices = body.get("choices") or [{}]
        choice = choices[0] if choices else {}
        message = choice.get("message") or {}
        text = _extract_text(message.get("content"))

        response_map[custom_id] = ProviderResponse(
            text=text,
            model=body.get("model", model_name),
            provider="openai",
            metadata={
                "custom_id": custom_id,
                "finish_reason": choice.get("finish_reason"),
                "usage": body.get("usage"),
            },
        )

    ordered_responses: List[ProviderResponse] = []
    for request in requests:
        custom_id = request.get("custom_id")
        response = response_map.get(custom_id)
        if not response:
            response = ProviderResponse(
                text="",
                model=request.get("model") or default_model,
                provider="openai",
                metadata={
                    "custom_id": custom_id,
                    "error": "Result missing for batch request",
                    "error_type": "MissingResult",
                },
            )
        ordered_responses.append(response)

    return ordered_responses


def prepare_openai_batch_requests(
    provider_instance: Any,
    requests: List[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Prepare requests for OpenAI Batch API.

    Args:
        provider_instance: The OpenAI provider instance.
        requests: List of batch request dictionaries.

    Returns:
        Tuple of (batch_requests, request_map) for API submission.

    Raises:
        ValidationError: If requests are malformed.
    """
    default_model = provider_instance._model_config.model_name if provider_instance._model_config else "gpt-4o-mini"
    batch_requests: List[Dict[str, Any]] = []
    request_map: Dict[str, Dict[str, Any]] = {}

    for request in requests:
        custom_id = request.get("custom_id")
        if not custom_id:
            raise ValidationError("Batch request missing custom_id", field="custom_id")

        messages = request.get("messages")
        if messages:
            messages = [dict(message) for message in messages]

        prompt = request.get("prompt")
        if not messages and prompt:
            messages = [{"role": "user", "content": prompt}]

        if not messages:
            raise ValidationError("Batch request missing prompt or messages", field=custom_id)

        system_prompt = request.get("system_prompt")
        if system_prompt:
            messages.insert(0, {"role": "system", "content": system_prompt})

        model_name = request.get("model") or default_model
        model_config = provider_instance._model_config
        if model_config and model_config.model_name == model_name:
            is_reasoning_model = bool(model_config.is_reasoning_model)
        else:
            is_reasoning_model = provider_instance._is_reasoning_model(model_name)

        body = {
            "model": model_name,
            "messages": messages,
        }

        for optional_key in ("temperature", "max_tokens", "top_p"):
            if optional_key in request and request[optional_key] is not None:
                if optional_key == "max_tokens":
                    # OpenAI reasoning models (o-series / gpt-5) expect ``max_completion_tokens``.
                    if is_reasoning_model:
                        body["max_completion_tokens"] = request[optional_key]
                    else:
                        body["max_tokens"] = request[optional_key]
                else:
                    body[optional_key] = request[optional_key]

        batch_requests.append({"custom_id": custom_id, "body": body})
        request_map[custom_id] = request

    return batch_requests, request_map


__all__ = ["process_openai_batch_response", "prepare_openai_batch_requests"]
