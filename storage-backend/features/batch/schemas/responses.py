"""Response schemas for batch operations."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class BatchJobResponse(BaseModel):
    """Represents a batch job status payload."""

    job_id: str
    provider: str
    model: str
    status: str
    request_count: int
    succeeded_count: int
    failed_count: int
    cancelled_count: int
    expired_count: int
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    expires_at: Optional[datetime]
    results_url: Optional[str]
    error_message: Optional[str]
    metadata: Optional[Dict[str, Any]] = Field(default=None, alias="metadata_payload")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class BatchJobListResponse(BaseModel):
    """Response for listing batches."""

    jobs: list[BatchJobResponse]
    total: int
    limit: int
    offset: int


__all__ = ["BatchJobResponse", "BatchJobListResponse"]
