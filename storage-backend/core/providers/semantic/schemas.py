"""Pydantic schemas for semantic search."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class SearchResult:
    """Single semantic search result.

    Represents one message retrieved from the vector database together with
    its relevance score and metadata payload.
    """

    message_id: int
    """Message ID from MySQL (ChatMessagesNG.message_id)."""

    content: str
    """Message text content."""

    score: float
    """Relevance score (0.0 - 1.0, higher is more relevant)."""

    metadata: dict[str, Any]
    """Additional metadata (session_id, user_id, tags, dates, etc.)."""

    def to_dict(self) -> dict[str, Any]:
        """Convert the result into a serialisable dictionary."""
        return {
            "message_id": self.message_id,
            "content": self.content,
            "score": self.score,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class SearchRequest:
    """Semantic search request parameters.

    Encapsulates all parameters needed to perform a semantic search with
    optional metadata filtering.
    """

    query: str
    """Search query text (will be embedded for semantic matching)."""

    customer_id: int
    """User ID (required for security - isolates user data)."""

    limit: int = 10
    """Maximum number of results to return (1-100)."""

    score_threshold: float | None = None
    """Minimum relevance score (0.0-1.0). None uses provider default."""

    search_mode: str = "hybrid"
    """Search strategy: 'hybrid', 'semantic', or 'keyword'."""

    filters: dict[str, Any] | None = None
    """Additional filters (for internal use by service layer)."""

    tags: list[str] | None = None
    """Filter by message tags (e.g., ['daily_journal', 'business_ideas'])."""

    date_range: tuple[str, str] | None = None
    """Filter by date range (ISO format: (start, end))."""

    message_type: str | None = None
    """Filter by message type: 'user' | 'assistant' | 'both' (None = both)."""

    session_ids: list[str | int] | None = None
    """Filter by specific session identifiers."""

    collection_name: str | None = None
    """Optional override for provider collection (internal use only)."""

    def __post_init__(self) -> None:
        """Validate parameters after initialisation."""
        if self.limit < 1 or self.limit > 100:
            raise ValueError("limit must be between 1 and 100")

        if (
            self.score_threshold is not None
            and (self.score_threshold < 0 or self.score_threshold > 1)
        ):
            raise ValueError("score_threshold must be between 0 and 1")

        if self.message_type and self.message_type not in {"user", "assistant", "both"}:
            raise ValueError("message_type must be 'user', 'assistant', or 'both'")

        valid_modes = {"hybrid", "semantic", "keyword"}
        if self.search_mode not in valid_modes:
            raise ValueError(
                f"Invalid search_mode: {self.search_mode}. Must be one of: {valid_modes}"
            )
