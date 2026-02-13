"""Batch operations for Gemini provider."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

from core.exceptions import ValidationError
from core.pydantic_schemas import ProviderResponse

logger = logging.getLogger(__name__)


def _extract_text(response_obj: Any) -> str:
    """Extract text content from Gemini response."""
    if response_obj is None:
        return ""
    if isinstance(response_obj, dict):
        candidates = response_obj.get("candidates")
        if isinstance(candidates, list) and candidates:
            candidate = candidates[0]
            content = candidate.get("content") if isinstance(candidate, dict) else None
            if isinstance(content, dict):
                parts = content.get("parts")
                if isinstance(parts, list):
                    for part in parts:
                        text_value = part.get("text") if isinstance(part, dict) else None
                        if text_value:
                            return text_value
        text_value = response_obj.get("text")
        if text_value:
            return text_value
    text = getattr(response_obj, "text", None)
    if text:
        return text
    candidates = getattr(response_obj, "candidates", None)
    if candidates:
        candidate = candidates[0]
        content = getattr(candidate, "content", None)
        if content and getattr(content, "parts", None):
            for part in content.parts:
                part_text = getattr(part, "text", None)
                if part_text:
                    return part_text
    return ""


async def process_gemini_batch_response(
    provider_instance: Any,
    requests: List[Dict[str, Any]],
    results: List[Dict[str, Any]],
) -> List[ProviderResponse]:
    """Process Gemini batch API results into ProviderResponse objects.

    Args:
        provider_instance: The Gemini provider instance.
        requests: Original batch requests.
        results: Raw results from Gemini batch API.

    Returns:
        List of ProviderResponse objects in request order.
    """
    default_model = provider_instance._model_config.model_name if provider_instance._model_config else "gemini-2.5-flash"

    # Inline responses are returned in request order (no keys)
    # Results and requests should have same length and order
    ordered: List[ProviderResponse] = []

    for index, request_data in enumerate(requests):
        custom_id = request_data.get("custom_id")

        # Get corresponding result by index
        if index >= len(results):
            ordered.append(ProviderResponse(
                text="",
                model=request_data.get("model") or default_model,
                provider="google",
                metadata={
                    "custom_id": custom_id,
                    "error": "Result missing for batch request",
                    "error_type": "MissingResult",
                },
            ))
            continue

        result = results[index]

        # Check for error in result
        if result.get("error"):
            ordered.append(ProviderResponse(
                text="",
                model=request_data.get("model") or default_model,
                provider="google",
                metadata={
                    "custom_id": custom_id,
                    "error": str(result["error"]),
                    "error_type": "batch_error",
                },
            ))
            continue

        # Extract response
        api_response = result.get("response")
        candidates = getattr(api_response, "candidates", None)
        finish_reason = None
        if candidates:
            first_candidate = candidates[0]
            finish_reason = getattr(first_candidate, "finish_reason", None)

        ordered.append(ProviderResponse(
            text=_extract_text(api_response),
            model=request_data.get("model") or default_model,
            provider="google",
            metadata={
                "custom_id": custom_id,
                "finish_reason": finish_reason,
            },
        ))

    logger.info("Completed Gemini batch with %d responses", len(ordered))
    return ordered


def transform_to_gemini_format(
    requests: List[Dict[str, Any]],
    default_model: str,
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Transform generic batch requests into Gemini inline format.

    Args:
        requests: List of batch request dictionaries.
        default_model: Default model to use if not specified in request.

    Returns:
        Tuple of (gemini_requests, request_map) for API submission.

    Raises:
        ValidationError: If requests are malformed.
    """
    gemini_requests: List[Dict[str, Any]] = []
    request_map: Dict[str, Dict[str, Any]] = {}

    def _build_contents(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        contents: List[Dict[str, Any]] = []
        messages = payload.get("messages")
        if messages:
            for message in messages:
                role = message.get("role", "user")
                content = message.get("content", "")
                parts: List[Dict[str, str]] = []
                if isinstance(content, list):
                    for entry in content:
                        if isinstance(entry, dict) and "text" in entry:
                            parts.append({"text": entry["text"]})
                        else:
                            parts.append({"text": str(entry)})
                elif isinstance(content, dict) and "text" in content:
                    parts.append({"text": content["text"]})
                else:
                    parts.append({"text": str(content)})

                contents.append({"role": role, "parts": parts})
        else:
            prompt_value = payload.get("prompt")
            if not prompt_value:
                raise ValidationError("Batch request missing prompt or messages", field=payload.get("custom_id"))
            contents.append({"role": "user", "parts": [{"text": prompt_value}]})

        return contents

    for request in requests:
        custom_id = request.get("custom_id")
        if not custom_id:
            raise ValidationError("Batch request missing custom_id", field="custom_id")

        contents = _build_contents(request)
        # For inline requests, use bare format with contents and optional config
        gemini_request: Dict[str, Any] = {
            "contents": contents,
        }

        # Config goes at top level (not generation_config)
        config: Dict[str, Any] = {}
        if "temperature" in request and request["temperature"] is not None:
            config["temperature"] = request["temperature"]
        if "max_tokens" in request and request["max_tokens"] is not None:
            config["max_output_tokens"] = request["max_tokens"]

        system_prompt = request.get("system_prompt")
        if system_prompt:
            config["system_instruction"] = {"parts": [{"text": system_prompt}]}

        if config:
            gemini_request["config"] = config

        gemini_requests.append(gemini_request)
        request_map[custom_id] = request

        logger.debug(
            "Transformed request for Gemini batch",
            extra={
                "custom_id": custom_id,
                "has_config": bool(config),
            },
        )

    return gemini_requests, request_map


__all__ = ["process_gemini_batch_response", "transform_to_gemini_format"]