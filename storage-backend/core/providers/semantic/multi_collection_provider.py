"""Provider wrapper that indexes into multiple Qdrant collections."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Iterable

from qdrant_client import models
from qdrant_client.models import Distance, PayloadSchemaType, PointIdsList, VectorParams

from config.semantic_search.utils import get_collection_for_mode
from core.exceptions import ProviderError

from .base import BaseSemanticProvider
from .indexing import MultiCollectionIndexing
from .schemas import SearchRequest, SearchResult

logger = logging.getLogger(__name__)


class MultiCollectionSemanticProvider(BaseSemanticProvider):
    """Wraps a base provider to index both semantic-only and hybrid collections."""

    def __init__(self, primary_provider: BaseSemanticProvider) -> None:
        self.primary_provider = primary_provider
        self.client = getattr(primary_provider, "client", None)
        self.embedding_provider = getattr(primary_provider, "embedding_provider", None)
        self.sparse_provider = getattr(primary_provider, "sparse_provider", None)
        self.circuit_breaker = getattr(primary_provider, "circuit_breaker", None)
        self.hybrid_collection = get_collection_for_mode("hybrid")
        self.semantic_collection = get_collection_for_mode("semantic")
        self.collection_name = self.hybrid_collection
        self.indexing = MultiCollectionIndexing(
            primary_provider=primary_provider,
            client=self.client,
            embedding_provider=self.embedding_provider,
            sparse_provider=self.sparse_provider,
            circuit_breaker=self.circuit_breaker,
            hybrid_collection=self.hybrid_collection,
            semantic_collection=self.semantic_collection,
        )

        logger.info(
            "Initialised multi-collection semantic provider",
            extra={
                "semantic_collection": self.semantic_collection,
                "hybrid_collection": self.hybrid_collection,
            },
        )

    # ------------------------------------------------------------------
    # Search delegates
    # ------------------------------------------------------------------
    async def search(self, request: SearchRequest) -> list[SearchResult]:
        return await self.primary_provider.search(request)

    async def health_check(self) -> dict[str, Any]:
        return await self.primary_provider.health_check()

    # ------------------------------------------------------------------
    # Indexing operations
    # ------------------------------------------------------------------
    async def index(self, message_id: int, content: str, metadata: dict[str, Any]) -> None:
        await self.indexing.index(message_id, content, metadata)

    async def bulk_index(
        self,
        messages: list[tuple[int, str, dict[str, Any]]],
        batch_size: int = 100,
    ) -> None:
        await self.indexing.bulk_index(messages, batch_size=batch_size)

    async def update(self, message_id: int, content: str, metadata: dict[str, Any]) -> None:
        await self.indexing.update(message_id, content, metadata)

    async def delete(self, message_id: int) -> None:
        await self.indexing.delete(message_id)

    async def create_collection(self) -> None:
        await self.primary_provider.create_collection()
        await self.indexing.ensure_semantic_collection()



__all__ = ["MultiCollectionSemanticProvider"]
