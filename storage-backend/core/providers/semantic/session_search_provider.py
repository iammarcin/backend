"""Qdrant provider dedicated to session-level search."""

from __future__ import annotations

import hashlib
import logging
from enum import Enum
from typing import Any, Dict, List, Optional

from qdrant_client import AsyncQdrantClient, models

from config.semantic_search.qdrant import QDRANT_COLLECTION_NAME_SESSIONS
from core.clients.ai import ai_clients, get_openai_async_client
from core.config import settings
from core.exceptions import ProviderError
from core.providers.semantic.embeddings import OpenAIEmbeddingProvider

logger = logging.getLogger(__name__)

COLLECTION_NAME = QDRANT_COLLECTION_NAME_SESSIONS


class SessionSearchType(str, Enum):
    """Search behavior offered by the session provider."""

    DENSE = "dense"
    HYBRID = "hybrid"
    SPARSE = "sparse"


class SessionSearchResult:
    """Container for session search results."""

    def __init__(self, payload: Dict[str, Any], score: float):
        self.payload = payload
        self.score = score

    def to_dict(self) -> Dict[str, Any]:
        return {
            **self.payload,
            "score": self.score,
        }


class SessionSearchProvider:
    """Qdrant-powered search over session summaries."""

    def __init__(
        self,
        *,
        qdrant_client: AsyncQdrantClient | None = None,
        embedding_provider: OpenAIEmbeddingProvider | None = None,
    ) -> None:
        self.qdrant_client = qdrant_client or AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
            check_compatibility=False,
        )
        if embedding_provider is not None:
            self.embedding_provider = embedding_provider
        else:
            client = ai_clients.get("openai_async") or get_openai_async_client()
            self.embedding_provider = OpenAIEmbeddingProvider(client=client)
        self._owns_client = qdrant_client is None

    async def close(self) -> None:
        if self._owns_client:
            await self.qdrant_client.close()

    async def _generate_embedding(self, text: str) -> List[float]:
        try:
            return await self.embedding_provider.generate(text)
        except Exception as exc:  # pragma: no cover - defensive
            raise ProviderError(f"Failed to generate embedding: {exc}") from exc

    def _generate_sparse_vector(self, text: str) -> models.SparseVector:
        tokens = text.lower().split()
        counts: dict[str, int] = {}
        for token in tokens:
            if len(token) <= 2:
                continue
            counts[token] = counts.get(token, 0) + 1

        indices: list[int] = []
        values: list[float] = []
        for token, count in counts.items():
            hashed = int(hashlib.md5(token.encode()).hexdigest()[:8], 16)
            indices.append(hashed % 100000)
            values.append(float(count))

        return models.SparseVector(indices=indices, values=values)

    def _build_filter(
        self,
        customer_id: int,
        topics_filter: Optional[List[str]],
        entities_filter: Optional[List[str]],
    ) -> models.Filter:
        conditions: list[models.FieldCondition] = [
            models.FieldCondition(
                key="customer_id",
                match=models.MatchValue(value=customer_id),
            )
        ]

        if topics_filter:
            for topic in topics_filter:
                conditions.append(
                    models.FieldCondition(
                        key="key_topics",
                        match=models.MatchValue(value=topic),
                    )
                )

        if entities_filter:
            for entity in entities_filter:
                conditions.append(
                    models.FieldCondition(
                        key="main_entities",
                        match=models.MatchValue(value=entity),
                    )
                )

        return models.Filter(must=conditions)

    async def search(
        self,
        query: str,
        customer_id: int,
        *,
        search_type: SessionSearchType,
        limit: int = 10,
        topics_filter: Optional[List[str]] = None,
        entities_filter: Optional[List[str]] = None,
    ) -> List[SessionSearchResult]:
        """Execute a session-level search."""

        query_filter = self._build_filter(customer_id, topics_filter, entities_filter)

        try:
            if search_type == SessionSearchType.DENSE:
                dense_vector = await self._generate_embedding(query)
                response = await self.qdrant_client.query_points(
                    collection_name=COLLECTION_NAME,
                    query=dense_vector,
                    using="dense",
                    limit=limit,
                    with_payload=True,
                    query_filter=query_filter,
                )
                hits = response.points
            elif search_type == SessionSearchType.SPARSE:
                sparse_vector = self._generate_sparse_vector(query)
                response = await self.qdrant_client.query_points(
                    collection_name=COLLECTION_NAME,
                    query=sparse_vector,
                    using="sparse",
                    limit=limit,
                    with_payload=True,
                    query_filter=query_filter,
                )
                hits = response.points
            else:
                dense_vector = await self._generate_embedding(query)
                sparse_vector = self._generate_sparse_vector(query)
                response = await self.qdrant_client.query_points(
                    collection_name=COLLECTION_NAME,
                    prefetch=[
                        models.Prefetch(
                            query=dense_vector,
                            using="dense",
                            limit=limit * 2,
                            filter=query_filter,
                        ),
                        models.Prefetch(
                            query=sparse_vector,
                            using="sparse",
                            limit=limit * 2,
                            filter=query_filter,
                        ),
                    ],
                    query=models.FusionQuery(fusion=models.Fusion.RRF),
                    limit=limit,
                    with_payload=True,
                )
                hits = response.points

            results: list[SessionSearchResult] = []
            for hit in hits:
                if not hit.payload:
                    continue
                results.append(SessionSearchResult(payload=hit.payload, score=hit.score or 0.0))
            return results
        except Exception as exc:
            logger.error("Session search failed: %s", exc)
            raise ProviderError(f"Session search failed: {exc}") from exc
