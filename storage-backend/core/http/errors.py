"""Utilities for formatting structured HTTP error responses."""

from __future__ import annotations

from typing import Any, Dict

from core.exceptions import (
    ConfigurationError,
    ProviderError,
    ServiceError,
    ValidationError,
)


def _build_error_payload(
    *,
    error: str,
    message: str,
    context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"error": error, "message": message}
    if context:
        payload["context"] = context
    return payload


def format_validation_error(exc: ValidationError) -> Dict[str, Any]:
    """Return a standard payload for :class:`ValidationError`."""

    context = {"field": exc.field} if getattr(exc, "field", None) else None
    return _build_error_payload(
        error="validation_error",
        message=str(exc),
        context=context,
    )


def format_configuration_error(exc: ConfigurationError) -> Dict[str, Any]:
    """Return a standard payload for :class:`ConfigurationError`."""

    context = {"key": exc.key} if getattr(exc, "key", None) else None
    return _build_error_payload(
        error="configuration_error",
        message=str(exc),
        context=context,
    )


def format_provider_error(exc: ProviderError) -> Dict[str, Any]:
    """Return a standard payload for :class:`ProviderError`."""

    context = {
        key: value
        for key, value in {
            "provider": getattr(exc, "provider", None),
            "original_error": str(exc.original_error)
            if getattr(exc, "original_error", None)
            else None,
        }.items()
        if value
    }

    return _build_error_payload(
        error="provider_error",
        message=str(exc),
        context=context or None,
    )


def format_service_error(exc: ServiceError) -> Dict[str, Any]:
    """Return a standard payload for generic service errors."""

    return _build_error_payload(
        error="service_error",
        message=str(exc),
    )


__all__ = [
    "format_configuration_error",
    "format_provider_error",
    "format_service_error",
    "format_validation_error",
]

