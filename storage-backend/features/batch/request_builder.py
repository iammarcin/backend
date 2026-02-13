"""Request building utilities for batch operations."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from core.providers.registry import get_model_config
from features.batch.schemas.requests import CreateBatchRequest

logger = logging.getLogger(__name__)


class BatchRequestBuilder:
    """Handles building provider requests from batch requests."""

    @staticmethod
    def _resolve_model_name(requested_model: str | None, default_model_name: str) -> str:
        """Convert aliases into provider-ready model identifiers."""

        if not requested_model:
            return default_model_name

        try:
            return get_model_config(requested_model).model_name
        except Exception:
            logger.warning(
                "Unable to resolve batch model %s, falling back to %s",
                requested_model,
                default_model_name,
            )
            return default_model_name

    @classmethod
    def build_provider_requests(cls, request: CreateBatchRequest) -> List[Dict[str, Any]]:
        """Normalize batch request payloads for providers."""

        provider_requests: List[Dict[str, Any]] = []
        default_model_name = get_model_config(request.model).model_name

        for item in request.requests:
            provider_requests.append(
                {
                    "custom_id": item.custom_id,
                    "prompt": item.prompt,
                    "model": cls._resolve_model_name(item.model, default_model_name),
                    "temperature": item.temperature,
                    "max_tokens": item.max_tokens,
                    "system_prompt": item.system_prompt,
                    "messages": item.messages,
                }
            )

        return provider_requests


__all__ = ["BatchRequestBuilder"]
