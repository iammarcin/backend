"""Base interface for semantic search providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .schemas import SearchRequest, SearchResult


class BaseSemanticProvider(ABC):
    """Base interface for semantic search providers.

    All concrete implementations (Qdrant, Pinecone, Chroma, etc.) must
    implement these methods to ensure consistent behaviour across providers.
    """

    @abstractmethod
    async def search(self, request: SearchRequest) -> list[SearchResult]:
        """Perform semantic search and return ranked results."""

    @abstractmethod
    async def index(self, message_id: int, content: str, metadata: dict[str, Any]) -> None:
        """Index a single message with its metadata."""

    @abstractmethod
    async def bulk_index(
        self,
        messages: list[tuple[int, str, dict[str, Any]]],
        batch_size: int = 100,
    ) -> None:
        """Index multiple messages in batch (for backfilling existing data)."""

    @abstractmethod
    async def update(self, message_id: int, content: str, metadata: dict[str, Any]) -> None:
        """Update an existing indexed message."""

    @abstractmethod
    async def delete(self, message_id: int) -> None:
        """Remove a message from the index."""

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """Verify connection to vector database and return component status."""

    @abstractmethod
    async def create_collection(self) -> None:
        """Create the collection/index if it doesn't exist."""
