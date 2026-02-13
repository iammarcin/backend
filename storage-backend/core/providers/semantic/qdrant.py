"""Qdrant implementation of semantic search provider."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from qdrant_client import AsyncQdrantClient, models
from qdrant_client.models import Distance, PayloadSchemaType, VectorParams

from core.exceptions import ProviderError

from .base import BaseSemanticProvider
from .bm25 import BM25SparseVectorProvider
from .circuit_breaker import CircuitBreaker
from .embeddings import EmbeddingProvider
from .qdrant_health import run_health_check
from .qdrant_indexing import bulk_index, create_collection, delete_message, index_message
from .qdrant_search import QdrantSearch
from .schemas import SearchRequest, SearchResult


logger = logging.getLogger(__name__)


class QdrantSemanticProvider(BaseSemanticProvider):
    """Qdrant implementation of semantic search provider."""

    def __init__(
        self,
        *,
        client: AsyncQdrantClient,
        collection_name: str,
        embedding_provider: EmbeddingProvider,
        sparse_provider: BM25SparseVectorProvider,  # New
        timeout: float = 10.0,
    ) -> None:
        self.client = client
        self.collection_name = collection_name
        self.embedding_provider = embedding_provider
        self.sparse_provider = sparse_provider  # New
        self.timeout = timeout
        self.circuit_breaker = CircuitBreaker(failure_threshold=5, timeout_seconds=60)
        self.search_engine = QdrantSearch(
            client=client,
            collection_name=collection_name,
            embedding_provider=embedding_provider,
            sparse_provider=sparse_provider,
            timeout=timeout,
            circuit_breaker=self.circuit_breaker,
        )
        self.logger = logger

        logger.info(
            "Initialised Qdrant semantic provider",
            extra={"collection_name": collection_name, "timeout": timeout},
        )

    # ------------------------------------------------------------------
    # Core search operations
    # ------------------------------------------------------------------
    async def search(self, request: SearchRequest) -> list[SearchResult]:
        """Execute search request for specified mode."""
        return await self.search_engine.search(request)


    # ------------------------------------------------------------------
    # Indexing operations
    # ------------------------------------------------------------------
    async def index(self, message_id: int, content: str, metadata: dict[str, Any]) -> None:
        await index_message(self, message_id, content, metadata)

    async def bulk_index(
        self,
        messages: list[tuple[int, str, dict[str, Any]]],
        batch_size: int = 100,
    ) -> None:
        await bulk_index(self, messages, batch_size=batch_size)

    async def update(self, message_id: int, content: str, metadata: dict[str, Any]) -> None:
        await self.index(message_id, content, metadata)
        logger.debug("Updated message", extra={"message_id": message_id})

    async def delete(self, message_id: int) -> None:
        await delete_message(self, message_id)

    # ------------------------------------------------------------------
    # Health + collection management
    # ------------------------------------------------------------------
    async def health_check(self) -> dict[str, Any]:
        return await run_health_check(
            client=self.client,
            collection_name=self.collection_name,
            embedding_provider=self.embedding_provider,
            circuit_breaker=self.circuit_breaker,
        )

    async def create_collection(self) -> None:
        await create_collection(self)

    async def create_payload_indexes(self) -> None:
        indexes = [
            ("customer_id", PayloadSchemaType.INTEGER),
            ("session_id", PayloadSchemaType.KEYWORD),
            ("tags", PayloadSchemaType.KEYWORD),
            ("created_at", PayloadSchemaType.DATETIME),
            ("message_type", PayloadSchemaType.KEYWORD),
            ("content_hash", PayloadSchemaType.KEYWORD),
        ]

        for field_name, field_schema in indexes:
            try:
                await self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field_name,
                    field_schema=field_schema,
                )
                logger.debug("Created payload index", extra={"field": field_name})
            except Exception:
                logger.warning(
                    "Failed to create payload index", extra={"field": field_name}, exc_info=True
                )

    # ------------------------------------------------------------------
    # Helpers consumed by indexing utilities
    # ------------------------------------------------------------------
    @property
    def vector_params(self) -> VectorParams:
        return VectorParams(
            size=self.embedding_provider.dimensions,
            distance=Distance.COSINE,
        )


__all__ = ["QdrantSemanticProvider"]
