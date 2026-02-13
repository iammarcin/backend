"""Service layer for batch job orchestration."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from config.batch.defaults import BATCH_RESULT_EXPIRY_DAYS
from config.batch.utils import validate_batch_size
from core.exceptions import NotFoundError, ProviderError, ValidationError
from core.providers.registry import get_model_config
from core.providers.resolvers import get_text_provider
from core.pydantic_schemas import ProviderResponse
from features.batch.monitoring.batch_metrics import BatchMetrics
from features.batch.repositories.batch_job_repository import BatchJobRepository
from features.batch.request_builder import BatchRequestBuilder
from features.batch.schemas.requests import CreateBatchRequest
from features.batch.schemas.responses import BatchJobResponse
from features.batch.status_handler import BatchStatusHandler

logger = logging.getLogger(__name__)


class BatchService:
    """Coordinates batch provider submissions and persistence."""

    def __init__(self, repository: BatchJobRepository) -> None:
        self.repository = repository

    async def submit_batch(self, request: CreateBatchRequest, *, customer_id: int) -> BatchJobResponse:
        """Backward-compatible helper that submits and waits for completion."""

        queued_job = await self.submit_batch_async(request, customer_id=customer_id)
        return await self.poll_and_complete_batch(
            queued_job.job_id,
            customer_id=customer_id,
        )

    async def submit_batch_async(self, request: CreateBatchRequest, *, customer_id: int) -> BatchJobResponse:
        """Submit a new batch job without waiting for completion."""

        try:
            model_config = get_model_config(request.model)
        except Exception as exc:
            raise ValidationError(f"Invalid model: {request.model}") from exc

        provider_name = model_config.provider_name
        if not getattr(model_config, "supports_batch_api", False):
            raise ValidationError(
                f"Model {request.model} does not support batch API. Only OpenAI, Anthropic, and Gemini batches are available.",
            )

        if not validate_batch_size(provider_name, len(request.requests)):
            raise ValidationError(
                f"Batch size {len(request.requests)} exceeds limit for provider {provider_name}",
            )

        job_summary = {
            "customer_id": customer_id,
            "model": request.model,
            "provider": provider_name,
            "request_count": len(request.requests),
            "description": request.description,
        }

        logger.info("Batch submission started", extra=job_summary)
        BatchMetrics.track_submission(
            provider=provider_name,
            model=request.model,
            request_count=len(request.requests),
        )

        provider_requests = BatchRequestBuilder.build_provider_requests(request)
        job_id = f"batch_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"

        metadata_payload = {
            "description": request.description,
            "provider_requests": provider_requests,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }

        await self.repository.create(
            job_id=job_id,
            customer_id=customer_id,
            provider=provider_name,
            model=request.model,
            request_count=len(request.requests),
            metadata=metadata_payload,
        )
        await self.repository.session.commit()

        refreshed = await self.repository.get_by_job_id(job_id)
        if refreshed is None:
            raise NotFoundError(f"Batch job {job_id} not found after submission")
        return BatchJobResponse.model_validate(refreshed)

    async def poll_and_complete_batch(
        self,
        job_id: str,
        *,
        customer_id: int,
        poll_interval: Optional[int] = None,
        timeout_seconds: Optional[int] = None,
    ) -> BatchJobResponse:
        """Poll batch status until completion and persist results."""

        batch_job = await self.repository.get_by_job_id(job_id)
        if batch_job is None or batch_job.customer_id != customer_id:
            raise NotFoundError(f"Batch job {job_id} not found")

        if batch_job.status in {"completed", "failed", "cancelled", "expired"}:
            return BatchJobResponse.model_validate(batch_job)

        raw_metadata = getattr(batch_job, "metadata_payload", {}) or {}
        metadata = dict(raw_metadata)
        provider_requests = metadata.get("provider_requests")
        description = metadata.get("description")
        if not provider_requests:
            raise ValidationError(f"Batch job {job_id} missing provider requests")

        settings: Dict[str, Dict[str, Any]] = {"text": {"model": batch_job.model}}
        provider = get_text_provider(settings)

        logger.info(
            "Starting provider batch processing",
            extra={
                "job_id": job_id,
                "provider": batch_job.provider,
                "model": batch_job.model,
                "request_count": len(provider_requests),
            },
        )

        processing_started_at = datetime.now(timezone.utc)
        await self.repository.update_status(
            job_id=job_id,
            status="processing",
            started_at=processing_started_at,
            commit=True,
        )

        _status_callback = await BatchStatusHandler.create_status_callback(job_id, self.repository)

        poll_kwargs = {}
        if poll_interval is not None:
            poll_kwargs["polling_interval"] = poll_interval
        if timeout_seconds is not None:
            poll_kwargs["timeout"] = timeout_seconds

        try:
            responses = await provider.generate_batch(
                requests=provider_requests,
                description=description,
                status_callback=_status_callback,
                **poll_kwargs,
            )
        except (ValidationError, ProviderError) as exc:
            logger.error(
                "Batch processing failed",
                extra={"job_id": job_id, "error": str(exc)},
                exc_info=True,
            )
            await self.repository.update_status(
                job_id=job_id,
                status="failed",
                completed_at=datetime.now(timezone.utc),
                error_message=str(exc),
                commit=True,
            )
            BatchMetrics.track_error(
                provider=batch_job.provider,
                model=batch_job.model,
                error_type=exc.__class__.__name__,
            )
            raise
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Unexpected batch provider failure")
            await self.repository.update_status(
                job_id=job_id,
                status="failed",
                completed_at=datetime.now(timezone.utc),
                error_message=str(exc),
                commit=True,
            )
            BatchMetrics.track_error(
                provider=batch_job.provider,
                model=batch_job.model,
                error_type=exc.__class__.__name__,
            )
            raise ProviderError("Batch submission failed", provider=batch_job.provider, original_error=exc) from exc

        await BatchStatusHandler.update_batch_completion(
            self.repository,
            job_id,
            responses,
            batch_job,
            processing_started_at,
        )

        refreshed = await self.repository.get_by_job_id(job_id)
        if refreshed is None:
            raise NotFoundError(f"Batch job {job_id} not found after completion")
        return BatchJobResponse.model_validate(refreshed)

    async def get_batch_status(self, job_id: str, *, customer_id: int) -> BatchJobResponse:
        """Return batch job metadata for a user."""

        batch_job = await self.repository.get_by_job_id(job_id)
        if batch_job is None or batch_job.customer_id != customer_id:
            raise NotFoundError(f"Batch job {job_id} not found")
        return BatchJobResponse.model_validate(batch_job)

    async def get_batch_results(self, job_id: str, *, customer_id: int) -> List[ProviderResponse]:
        """Return ProviderResponse entries stored for a completed job."""

        batch_job = await self.repository.get_by_job_id(job_id)
        if batch_job is None or batch_job.customer_id != customer_id:
            raise NotFoundError(f"Batch job {job_id} not found")

        if batch_job.status != "completed":
            raise ValidationError(f"Batch job {job_id} not completed (status: {batch_job.status})")

        if batch_job.expires_at:
            expires_at = batch_job.expires_at
            if isinstance(expires_at, datetime) and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expires_at:
                raise ValidationError(f"Batch job {job_id} results have expired")

        metadata = getattr(batch_job, "metadata_payload", {}) or {}
        response_data = metadata.get("responses", [])
        results: List[ProviderResponse] = []
        for entry in response_data:
            try:
                results.append(ProviderResponse(**entry))
            except Exception:
                logger.debug("Skipping invalid ProviderResponse payload for batch %s", job_id, exc_info=True)
        return results

    async def list_batches(
        self,
        *,
        customer_id: int,
        limit: int = 20,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List batch jobs for a user with optional status filtering."""

        jobs = await self.repository.list_by_customer(
            customer_id=customer_id,
            limit=limit,
            offset=offset,
            status=status,
        )
        payload = {
            "jobs": [BatchJobResponse.model_validate(job) for job in jobs],
            "total": len(jobs),
            "limit": limit,
            "offset": offset,
        }
        return payload

    async def cancel_batch(self, job_id: str, *, customer_id: int) -> BatchJobResponse:
        """Cancel an in-flight batch job."""

        batch_job = await self.repository.get_by_job_id(job_id)
        if batch_job is None or batch_job.customer_id != customer_id:
            raise NotFoundError(f"Batch job {job_id} not found")

        if batch_job.status in {"completed", "failed", "cancelled", "expired"}:
            raise ValidationError(f"Cannot cancel batch job in status: {batch_job.status}")

        await self.repository.update_status(
            job_id=job_id,
            status="cancelled",
            completed_at=datetime.now(timezone.utc),
            commit=True,
        )
        refreshed = await self.repository.get_by_job_id(job_id)
        if refreshed is None:
            raise NotFoundError(f"Batch job {job_id} not found")
        return BatchJobResponse.model_validate(refreshed)

