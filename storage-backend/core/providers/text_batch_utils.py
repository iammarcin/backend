"""Utility functions for text provider batch operations."""

from typing import Any, Dict, List

from core.exceptions import ProviderError
from core.pydantic_schemas import ProviderResponse


async def fallback_batch_generation(
    provider: Any,
    requests: List[Dict[str, Any]],
    **kwargs: Any,
) -> List[ProviderResponse]:
    """Fallback batch generation using sequential calls when batch API is not supported.

    Args:
        provider: The text provider instance.
        requests: Collection of request payloads that mimic generate() inputs.
        **kwargs: Additional provider-specific overrides passed to generate().

    Returns:
        Responses in the same order as the supplied requests.
    """
    results: List[ProviderResponse] = []
    for request in requests:
        custom_id = request.get("custom_id", "unknown")
        prompt = request.get("prompt")
        extra_params = {
            key: value
            for key, value in request.items()
            if key
            not in {
                "custom_id",
                "prompt",
                "model",
                "temperature",
                "max_tokens",
                "system_prompt",
                "messages",
            }
        }

        try:
            response = await provider.generate(
                prompt=prompt,
                model=request.get("model"),
                temperature=request.get("temperature", 0.1),
                max_tokens=request.get("max_tokens", 4096),
                system_prompt=request.get("system_prompt"),
                messages=request.get("messages"),
                **kwargs,
                **extra_params,
            )
            response.metadata = response.metadata or {}
            response.metadata["custom_id"] = custom_id
            results.append(response)
        except Exception as exc:  # pragma: no cover - defensive fallback
            error_response = ProviderResponse(
                text="",
                model=request.get("model", "unknown"),
                provider=provider.__class__.__name__.lower(),
                metadata={
                    "custom_id": custom_id,
                    "error": str(exc),
                    "error_type": exc.__class__.__name__,
                },
            )
            results.append(error_response)

    return results


__all__ = ["fallback_batch_generation"]