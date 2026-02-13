"""Batch operations for Anthropic provider."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from core.exceptions import ProviderError, ValidationError
from core.pydantic_schemas import ProviderResponse

logger = logging.getLogger(__name__)


def _extract_message_text(message: Any) -> str:
    """Extract text content from Anthropic message response."""
    contents = None
    if isinstance(message, dict):
        contents = message.get("content")
    else:
        contents = getattr(message, "content", None)
    if not contents:
        return ""
    chunks: List[str] = []
    for part in contents or []:
        if isinstance(part, dict):
            text = part.get("text")
        else:
            text = getattr(part, "text", None)
        if text:
            chunks.append(text)
    return "".join(chunks)


async def process_anthropic_batch_response(
    provider_instance: Any,
    requests: List[Dict[str, Any]],
    results: List[Dict[str, Any]],
) -> List[ProviderResponse]:
    """Process Anthropic batch API results into ProviderResponse objects.

    Args:
        provider_instance: The Anthropic provider instance.
        requests: Original batch requests.
        results: Raw results from Anthropic batch API.

    Returns:
        List of ProviderResponse objects in request order.
    """
    response_map: Dict[str, ProviderResponse] = {}
    for result in results:
        custom_id = result.get("custom_id")
        if not custom_id:
            continue

        payload = result.get("result")
        if isinstance(payload, dict):
            result_type = payload.get("type")
            message = payload.get("message")
            error_payload = payload.get("error")
        else:
            result_type = getattr(payload, "type", None)
            message = getattr(payload, "message", None)
            error_payload = getattr(payload, "error", None)

        if result_type == "succeeded":
            usage = message.get("usage") if isinstance(message, dict) else getattr(message, "usage", None)
            metadata = {
                "custom_id": custom_id,
                "stop_reason": message.get("stop_reason") if isinstance(message, dict) else getattr(message, "stop_reason", None),
                "usage": {
                    "input_tokens": (usage.get("input_tokens") if isinstance(usage, dict) else getattr(usage, "input_tokens", None)) if usage else None,
                    "output_tokens": (usage.get("output_tokens") if isinstance(usage, dict) else getattr(usage, "output_tokens", None)) if usage else None,
                },
            }
            message_model = message.get("model") if isinstance(message, dict) else getattr(message, "model", None)
            response_map[custom_id] = ProviderResponse(
                text=_extract_message_text(message),
                model=message_model or provider_instance._model_config.model_name if provider_instance._model_config else "claude-sonnet-4-5",
                provider="anthropic",
                metadata=metadata,
            )
            continue

        error_message = None
        error_type = None
        if isinstance(error_payload, dict):
            error_message = error_payload.get("message")
            error_type = error_payload.get("type")
        else:
            error_message = getattr(error_payload, "message", None)
            error_type = getattr(error_payload, "type", None)

        # Always dump for debugging when there's an error
        import json
        print(f"\n=== ANTHROPIC BATCH ERROR DEBUG ===")
        print(f"Custom ID: {custom_id}")
        print(f"Result type: {result_type}")
        print(f"Error payload: {error_payload}")
        print(f"Full result object:")
        print(json.dumps(result, indent=2, default=str))
        print("=== END DEBUG ===\n")

        final_error_msg = error_message or "Unknown error"
        final_error_type = error_type or "unknown"

        # Log error to stdout for scripts
        print(f"ERROR in Anthropic batch request '{custom_id}':")
        print(f"  Type: {final_error_type}")
        print(f"  Message: {final_error_msg}")
        print()

        logger.error(
            f"Anthropic batch request failed: {custom_id}",
            extra={
                "custom_id": custom_id,
                "error_type": final_error_type,
                "error_message": final_error_msg,
                "full_payload": str(payload)[:500],
            },
        )

        response_map[custom_id] = ProviderResponse(
            text="",
            model=provider_instance._model_config.model_name if provider_instance._model_config else "claude-sonnet-4-5",
            provider="anthropic",
            metadata={
                "custom_id": custom_id,
                "error": final_error_msg,
                "error_type": final_error_type,
            },
        )

    ordered: List[ProviderResponse] = []
    for request in requests:
        custom_id = request.get("custom_id")
        response = response_map.get(custom_id)
        if response is None:
            response = ProviderResponse(
                text="",
                model=request.get("model") or (provider_instance._model_config.model_name if provider_instance._model_config else "claude-sonnet-4-5"),
                provider="anthropic",
                metadata={
                    "custom_id": custom_id,
                    "error": "Result missing for batch request",
                    "error_type": "MissingResult",
                },
            )
        ordered.append(response)

    logger.info("Completed Anthropic batch with %d responses", len(ordered))
    return ordered


def prepare_anthropic_batch_requests(
    provider_instance: Any,
    requests: List[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Prepare requests for Anthropic Message Batches API.

    Args:
        provider_instance: The Anthropic provider instance.
        requests: List of batch request dictionaries.

    Returns:
        Tuple of (batch_requests, request_map) for API submission.

    Raises:
        ValidationError: If requests are malformed.
    """
    default_model = provider_instance._model_config.model_name if provider_instance._model_config else "claude-sonnet-4-5"
    batch_requests: List[Dict[str, Any]] = []
    request_map: Dict[str, Dict[str, Any]] = {}

    for request in requests:
        custom_id = request.get("custom_id")
        if not custom_id:
            raise ValidationError("Batch request missing custom_id", field="custom_id")

        messages = request.get("messages")
        if not messages:
            prompt = request.get("prompt")
            if not prompt:
                raise ValidationError("Batch request missing prompt or messages", field=custom_id)
            messages = [{"role": "user", "content": prompt}]

        system_prompt = request.get("system_prompt")
        params: Dict[str, Any] = {
            "model": request.get("model") or default_model,
            "messages": messages,
            "max_tokens": request.get("max_tokens", 4096),
        }

        if system_prompt:
            params["system"] = system_prompt
        if "temperature" in request and request["temperature"] is not None:
            params["temperature"] = request["temperature"]
        if "extra_params" in request and isinstance(request["extra_params"], dict):
            params.update(request["extra_params"])

        batch_requests.append({"custom_id": custom_id, "params": params})
        request_map[custom_id] = request

    return batch_requests, request_map


__all__ = ["process_anthropic_batch_response", "prepare_anthropic_batch_requests"]