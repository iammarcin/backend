"""HTTP routes for batch job operations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from core.auth import AuthContext, require_auth_context
from core.exceptions import NotFoundError, ProviderError, ValidationError
from core.pydantic_schemas import ApiResponse, ok as api_ok
from core.providers.registry import get_registry
from features.batch.dependencies import get_batch_job_repository
from features.batch.repositories.batch_job_repository import BatchJobRepository
from features.batch.schemas.requests import CreateBatchRequest
from features.batch.schemas.responses import BatchJobListResponse, BatchJobResponse
from features.batch.services import BatchService

router = APIRouter(prefix="/api/v1/batch", tags=["batch"])


def _get_service(repository: BatchJobRepository) -> BatchService:
    return BatchService(repository)


@router.post("/", response_model=ApiResponse[BatchJobResponse])
async def submit_batch_job(
    request: CreateBatchRequest,
    auth_context: AuthContext = Depends(require_auth_context),
    repository: BatchJobRepository = Depends(get_batch_job_repository),
) -> Dict:
    """Submit a new batch job and persist immediate results."""

    service = _get_service(repository)
    try:
        batch_job = await service.submit_batch(request=request, customer_id=auth_context["customer_id"])
        return api_ok("Batch job completed", data=batch_job)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.get("/{job_id}", response_model=ApiResponse[BatchJobResponse])
async def get_batch_status(
    job_id: str,
    auth_context: AuthContext = Depends(require_auth_context),
    repository: BatchJobRepository = Depends(get_batch_job_repository),
) -> Dict:
    """Retrieve batch job metadata."""

    service = _get_service(repository)
    try:
        batch_job = await service.get_batch_status(job_id, customer_id=auth_context["customer_id"])
        return api_ok("Batch job retrieved", data=batch_job)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{job_id}/results", response_model=ApiResponse[List[Dict]])
async def get_batch_results(
    job_id: str,
    auth_context: AuthContext = Depends(require_auth_context),
    repository: BatchJobRepository = Depends(get_batch_job_repository),
) -> Dict:
    """Return ProviderResponse payloads for a completed batch."""

    service = _get_service(repository)
    try:
        results = await service.get_batch_results(job_id, customer_id=auth_context["customer_id"])
        return api_ok("Batch results retrieved", data=[result.model_dump() for result in results])
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/health", response_model=ApiResponse[Dict[str, Any]])
async def batch_api_health() -> Dict:
    """Health check for Batch API provider coverage."""

    registry = get_registry()
    provider_status: Dict[str, Dict[str, Any]] = {}
    for provider in ["openai", "anthropic", "google"]:
        batch_models: List[str] = []
        for model_key in registry.list_models(provider_name=provider):
            try:
                config = registry.get_model_config(model_key)
            except Exception:
                continue
            if getattr(config, "supports_batch_api", False):
                batch_models.append(config.model_name)
        provider_status[provider] = {
            "available": bool(batch_models),
            "batch_supported": bool(batch_models),
            "batch_models": batch_models,
        }

    health_status = {
        "status": "healthy",
        "providers": provider_status,
    }
    return api_ok("Batch API health", data=health_status)


@router.get("/", response_model=ApiResponse[BatchJobListResponse])
async def list_batch_jobs(
    limit: int = 20,
    offset: int = 0,
    status_filter: Optional[str] = None,
    auth_context: AuthContext = Depends(require_auth_context),
    repository: BatchJobRepository = Depends(get_batch_job_repository),
) -> Dict:
    """List batch jobs owned by the authenticated customer."""

    service = _get_service(repository)
    result = await service.list_batches(
        customer_id=auth_context["customer_id"],
        limit=limit,
        offset=offset,
        status=status_filter,
    )
    payload = BatchJobListResponse(**result)
    return api_ok("Batch jobs retrieved", data=payload)


@router.post("/{job_id}/cancel", response_model=ApiResponse[BatchJobResponse])
async def cancel_batch_job(
    job_id: str,
    auth_context: AuthContext = Depends(require_auth_context),
    repository: BatchJobRepository = Depends(get_batch_job_repository),
) -> Dict:
    """Cancel a batch job that is still processing."""

    service = _get_service(repository)
    try:
        batch_job = await service.cancel_batch(job_id, customer_id=auth_context["customer_id"])
        return api_ok("Batch job cancelled", data=batch_job)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
