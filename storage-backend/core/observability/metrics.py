"""Structured logging helpers for audio transcription observability."""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional

try:  # pragma: no cover - optional dependency
    from prometheus_client import Counter, Histogram  # type: ignore
except Exception:  # pragma: no cover - optional dependency guard
    Counter = None  # type: ignore
    Histogram = None  # type: ignore


_logger = logging.getLogger("observability.audio")
_metrics_logger = logging.getLogger("observability.metrics")


def _build_payload(**fields: Any) -> Mapping[str, Any]:
    """Return a payload suitable for structured logging handlers."""

    return {
        "event": fields.pop("event"),
        "audio": fields,
    }


def record_transcription_success(
    *,
    provider: str,
    model: str | None,
    action: str,
    customer_id: int,
    filename: str | None,
    duration_seconds: float | None,
    elapsed_seconds: float,
    language: str | None,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    """Emit a structured log entry for a successful static transcription."""

    payload = _build_payload(
        event="static_transcription.completed",
        provider=provider,
        model=model,
        action=action,
        customer_id=customer_id,
        filename=filename,
        language=language,
        duration_seconds=duration_seconds,
        elapsed_ms=int(elapsed_seconds * 1000),
        metadata=dict(metadata or {}),
    )
    _logger.info("static_transcription_completed", extra={"observability": payload})


def record_transcription_failure(
    *,
    provider: str | None,
    model: str | None,
    action: str,
    customer_id: int,
    filename: str | None,
    elapsed_seconds: float,
    error: str,
) -> None:
    """Emit a structured log entry for a failed static transcription."""

    payload = _build_payload(
        event="static_transcription.failed",
        provider=provider,
        model=model,
        action=action,
        customer_id=customer_id,
        filename=filename,
        elapsed_ms=int(elapsed_seconds * 1000),
        error=error,
    )
    _logger.error("static_transcription_failed", extra={"observability": payload})


def track_metric(name: str, value: float = 1.0, *, tags: Optional[Mapping[str, Any]] = None) -> None:
    """Emit a lightweight metric event for ad-hoc tracking.

    Falls back to structured logging so downstream collectors can ingest the data.
    """

    payload = {
        "event": "metric",
        "metric": name,
        "value": value,
        "tags": dict(tags or {}),
    }
    _metrics_logger.info("metric_event", extra={"observability": payload})


__all__ = [
    "record_transcription_failure",
    "record_transcription_success",
    "track_metric",
]
