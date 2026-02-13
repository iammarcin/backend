"""Utility helpers for batch configuration."""

from __future__ import annotations

from config.batch.defaults import (
    BATCH_MAX_FILE_SIZE_MB_ANTHROPIC,
    BATCH_MAX_FILE_SIZE_MB_GEMINI,
    BATCH_MAX_FILE_SIZE_MB_OPENAI,
    BATCH_MAX_REQUESTS_ANTHROPIC,
    BATCH_MAX_REQUESTS_GEMINI,
    BATCH_MAX_REQUESTS_OPENAI,
)


def get_batch_max_requests(provider: str) -> int:
    """Return maximum requests per batch for a provider."""

    limits = {
        "openai": BATCH_MAX_REQUESTS_OPENAI,
        "anthropic": BATCH_MAX_REQUESTS_ANTHROPIC,
        "google": BATCH_MAX_REQUESTS_GEMINI,
        "gemini": BATCH_MAX_REQUESTS_GEMINI,
    }
    return limits.get(provider.lower(), 0)


def get_batch_max_file_size_mb(provider: str) -> int:
    """Return maximum file size in MB for a provider."""

    limits = {
        "openai": BATCH_MAX_FILE_SIZE_MB_OPENAI,
        "anthropic": BATCH_MAX_FILE_SIZE_MB_ANTHROPIC,
        "google": BATCH_MAX_FILE_SIZE_MB_GEMINI,
        "gemini": BATCH_MAX_FILE_SIZE_MB_GEMINI,
    }
    return limits.get(provider.lower(), 0)


def validate_batch_size(provider: str, request_count: int) -> bool:
    """Validate batch size against provider maximums."""

    max_requests = get_batch_max_requests(provider)
    if max_requests == 0:
        return True
    return request_count <= max_requests


__all__ = ["get_batch_max_requests", "get_batch_max_file_size_mb", "validate_batch_size"]
