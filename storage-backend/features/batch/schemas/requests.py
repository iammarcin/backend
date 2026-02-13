"""Request schemas for batch API operations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class BatchRequestItem(BaseModel):
    """Describes a single entry within a batch submission."""

    custom_id: str = Field(..., description="Unique identifier for this request")
    prompt: str = Field(..., description="Prompt text")
    model: Optional[str] = Field(None, description="Override model for this request")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, gt=0)
    system_prompt: Optional[str] = None
    messages: Optional[List[Dict[str, Any]]] = None


class CreateBatchRequest(BaseModel):
    """Payload for submitting a batch job."""

    requests: List[BatchRequestItem] = Field(..., min_length=1)
    model: str = Field(..., description="Default model for batch requests")
    description: Optional[str] = Field(None, max_length=500)


__all__ = ["BatchRequestItem", "CreateBatchRequest"]
