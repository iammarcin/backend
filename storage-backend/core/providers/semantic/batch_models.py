"""Models used for OpenAI Batch API embedding jobs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class BatchRequest:
    """Represents a single embedding request in a batch job."""

    custom_id: str
    input_text: str


@dataclass(slots=True)
class BatchResult:
    """Represents a single embedding response from a batch job."""

    custom_id: str
    embedding: list[float]
    error: str | None = None


__all__ = ["BatchRequest", "BatchResult"]
