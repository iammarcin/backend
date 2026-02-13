"""Status handling utilities for batch operations."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from features.batch.monitoring.batch_metrics import BatchMetrics

logger = logging.getLogger(__name__)


class BatchStatusHandler:
    """Handles batch job status updates and callbacks."""

    @staticmethod
    async def create_status_callback(job_id: str, repository: Any) -> Any:
        """Create a status callback function for batch polling."""

        status_map = {
            "queued": "queued",
            "in_progress": "processing",
            "processing": "processing",
            "finalizing": "processing",
            "completed": "completed",
            "failed": "failed",
            "cancelled": "cancelled",
            "expired": "expired",
        }
        last_status: Optional[str] = None

        async def _status_callback(status: str, batch: Any) -> None:
            nonlocal last_status
            normalized = status_map.get((status or "").lower(), "processing")
            if normalized == last_status:
                return
            last_status = normalized
            await repository.update_status(
                job_id=job_id,
                status=normalized,
                commit=True,
            )
            logger.info(
                "Provider reported batch status",
                extra={
                    "job_id": job_id,
                    "status": status,
                    "normalized_status": normalized,
                    "request_counts": getattr(batch, "request_counts", None),
                },
            )

        return _status_callback

    @staticmethod
    async def update_batch_completion(
        repository: Any,
        job_id: str,
        responses: list,
        batch_job: Any,
        processing_started_at: datetime,
    ) -> None:
        """Update batch job with completion details."""

        succeeded = sum(1 for response in responses if not response.has_error)
        failed = len(responses) - succeeded

        metadata = getattr(batch_job, "metadata_payload", {}) or {}
        metadata["responses"] = [response.model_dump() for response in responses]
        metadata.pop("provider_requests", None)
        await repository.update_metadata(job_id=job_id, metadata=metadata, commit=True)

        completed_at = datetime.now(timezone.utc)
        await repository.update_status(
            job_id=job_id,
            status="completed",
            completed_at=completed_at,
            commit=True,
        )
        await repository.update_counts(
            job_id=job_id,
            succeeded=succeeded,
            failed=failed,
            commit=True,
        )

        from config.batch.defaults import BATCH_RESULT_EXPIRY_DAYS
        from datetime import timedelta
        expires_at = completed_at + timedelta(days=BATCH_RESULT_EXPIRY_DAYS)
        await repository.set_expires_at(job_id=job_id, expires_at=expires_at, commit=True)

        duration_seconds = (completed_at - processing_started_at).total_seconds()
        BatchMetrics.track_completion(
            provider=batch_job.provider,
            model=batch_job.model,
            succeeded=succeeded,
            failed=failed,
            duration_seconds=duration_seconds,
        )

        logger.info(
            "Batch %s finished (%d succeeded, %d failed)",
            job_id,
            succeeded,
            failed,
            extra={
                "job_id": job_id,
                "provider": batch_job.provider,
                "model": batch_job.model,
            },
        )


__all__ = ["BatchStatusHandler"]