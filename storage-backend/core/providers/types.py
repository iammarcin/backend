"""Typed dict helpers for provider batch requests."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class BatchRequest(TypedDict, total=False):
    """Structure describing a single batch request."""

    custom_id: str
    prompt: str
    model: Optional[str]
    temperature: Optional[float]
    max_tokens: Optional[int]
    system_prompt: Optional[str]
    messages: Optional[List[Dict[str, Any]]]


class BatchJobMetadata(TypedDict):
    """Metadata describing a batch job lifecycle."""

    job_id: str
    provider: str
    model: str
    status: str
    request_count: int
    succeeded_count: int
    failed_count: int
    cancelled_count: int
    expired_count: int
    created_at: str
    completed_at: Optional[str]
    results_url: Optional[str]
    error_message: Optional[str]


__all__ = ["BatchRequest", "BatchJobMetadata"]
