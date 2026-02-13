"""Shared mixins and configuration for chat request models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class BaseChatRequest(BaseModel):
    """Base class for chat requests that enforces common configuration."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    customer_id: int = Field(..., ge=1)


__all__ = ["BaseChatRequest"]
