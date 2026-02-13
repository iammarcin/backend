"""Batch API monitoring metrics helpers."""

from __future__ import annotations

from core.observability.metrics import track_metric


class BatchMetrics:
    """Centralized helpers for tracking batch metrics."""

    @staticmethod
    def track_submission(provider: str, model: str, request_count: int) -> None:
        """Track a batch submission event."""

        track_metric("batch.submitted", 1, tags={"provider": provider, "model": model})
        track_metric("batch.request_count", request_count, tags={"provider": provider})

    @staticmethod
    def track_completion(
        provider: str,
        model: str,
        succeeded: int,
        failed: int,
        duration_seconds: float,
    ) -> None:
        """Track completion statistics for a batch."""

        track_metric("batch.completed", 1, tags={"provider": provider, "model": model})
        track_metric("batch.requests.succeeded", succeeded, tags={"provider": provider})
        track_metric("batch.requests.failed", failed, tags={"provider": provider})
        track_metric(
            "batch.duration_seconds",
            duration_seconds,
            tags={"provider": provider, "model": model},
        )

    @staticmethod
    def track_error(provider: str, model: str, error_type: str) -> None:
        """Track a batch error occurrence."""

        track_metric(
            "batch.failed",
            1,
            tags={"provider": provider, "model": model, "error_type": error_type},
        )

    @staticmethod
    def track_cost_savings(provider: str, estimated_savings_usd: float) -> None:
        """Track estimated cost savings for informational dashboards."""

        track_metric(
            "batch.cost_savings_usd",
            estimated_savings_usd,
            tags={"provider": provider},
        )
