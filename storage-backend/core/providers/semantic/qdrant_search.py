"""Search operations for Qdrant semantic provider."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from qdrant_client import models

from core.exceptions import ProviderError

from .qdrant_filters import build_filter
from .schemas import SearchRequest, SearchResult

logger = logging.getLogger(__name__)


class QdrantSearch:
    """Search operations for Qdrant semantic provider."""

    def __init__(self, client, collection_name, embedding_provider, sparse_provider, timeout, circuit_breaker):
        self.client = client
        self.collection_name = collection_name
        self.embedding_provider = embedding_provider
        self.sparse_provider = sparse_provider
        self.timeout = timeout
        self.circuit_breaker = circuit_breaker

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        """Execute search request for specified mode."""
        if not self.circuit_breaker.can_attempt():
            logger.warning("Circuit breaker open - skipping semantic search")
            return []

        try:
            if request.search_mode == "hybrid":
                results = await self._search_hybrid(request)
            elif request.search_mode == "semantic":
                results = await self._search_semantic_only(request)
            elif request.search_mode == "keyword":
                results = await self._search_keyword_only(request)
            else:  # pragma: no cover - validation prevents this
                raise ValueError(f"Unknown search mode: {request.search_mode}")

            self.circuit_breaker.record_success()
            logger.info(
                "Search completed",
                extra={
                    "mode": request.search_mode,
                    "results": len(results),
                    "collection": request.collection_name or self.collection_name,
                },
            )
            return results
        except ProviderError:
            self.circuit_breaker.record_failure()
            raise
        except asyncio.TimeoutError:
            self.circuit_breaker.record_failure()
            logger.error("Search timeout", extra={"timeout": self.timeout})
            return []
        except Exception:
            self.circuit_breaker.record_failure()
            logger.error("Search failed", exc_info=True)
            return []

    async def _search_hybrid(self, request: SearchRequest) -> list[SearchResult]:
        """Hybrid search using dense + sparse vectors with RRF fusion."""
        dense_embedding = await self.embedding_provider.generate(request.query)
        sparse_embedding = self.sparse_provider.generate(request.query)
        qdrant_filter = build_filter(request)
        collection_name = request.collection_name or self.collection_name

        logger.debug(
            "Executing hybrid search",
            extra={
                "limit": request.limit,
                "score_threshold": request.score_threshold,
                "customer_id": request.customer_id,
                "dense_dims": len(dense_embedding),
                "sparse_terms": len(sparse_embedding["indices"]),
                "collection": collection_name,
            },
        )

        hits = await asyncio.wait_for(
            self.client.query_points(
                collection_name=collection_name,
                prefetch=[
                    models.Prefetch(
                        query=models.SparseVector(
                            indices=sparse_embedding["indices"],
                            values=sparse_embedding["values"],
                        ),
                        using="sparse",
                        limit=request.limit * 2,
                        filter=qdrant_filter,
                    ),
                    models.Prefetch(
                        query=dense_embedding,
                        using="dense",
                        limit=request.limit * 2,
                        filter=qdrant_filter,
                    ),
                ],
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=request.limit,
                score_threshold=request.score_threshold,
                with_payload=True,
            ),
            timeout=self.timeout,
        )

        return self._process_hits(hits)

    async def _search_semantic_only(self, request: SearchRequest) -> list[SearchResult]:
        """Semantic-only search using dense embeddings."""
        dense_embedding = await self.embedding_provider.generate(request.query)
        qdrant_filter = build_filter(request)
        collection_name = request.collection_name or self.collection_name

        logger.debug(
            "Executing semantic-only search",
            extra={
                "limit": request.limit,
                "score_threshold": request.score_threshold,
                "customer_id": request.customer_id,
                "embedding_dims": len(dense_embedding),
                "collection": collection_name,
            },
        )

        hits = await asyncio.wait_for(
            self.client.query_points(
                collection_name=collection_name,
                query=dense_embedding,
                using="dense",
                limit=request.limit,
                score_threshold=request.score_threshold,
                query_filter=qdrant_filter,
                with_payload=True,
            ),
            timeout=self.timeout,
        )

        return self._process_hits(hits)

    async def _search_keyword_only(self, request: SearchRequest) -> list[SearchResult]:
        """Keyword-only search using sparse vectors."""
        sparse_embedding = self.sparse_provider.generate(request.query)
        qdrant_filter = build_filter(request)
        collection_name = request.collection_name or self.collection_name

        logger.debug(
            "Executing keyword-only search",
            extra={
                "limit": request.limit,
                "score_threshold": request.score_threshold,
                "customer_id": request.customer_id,
                "sparse_terms": len(sparse_embedding["indices"]),
                "collection": collection_name,
            },
        )

        hits = await asyncio.wait_for(
            self.client.query_points(
                collection_name=collection_name,
                query=models.SparseVector(
                    indices=sparse_embedding["indices"],
                    values=sparse_embedding["values"],
                ),
                using="sparse",
                limit=request.limit,
                score_threshold=request.score_threshold,
                query_filter=qdrant_filter,
                with_payload=True,
            ),
            timeout=self.timeout,
        )

        return self._process_hits(hits)

    def _process_hits(self, hits: models.QueryResponse) -> list[SearchResult]:
        """Convert Qdrant hits into SearchResult objects."""
        results: list[SearchResult] = []

        for hit in hits.points:
            payload = hit.payload or {}
            content = str(payload.get("content", ""))
            metadata = {key: value for key, value in payload.items() if key != "content"}
            raw_id = hit.id if hit.id is not None else payload.get("message_id")

            try:
                message_id = int(raw_id)
            except (TypeError, ValueError):
                logger.warning(
                    "Skipping search result with invalid message id",
                    extra={"raw_id": raw_id},
                )
                continue

            score = float(hit.score) if hit.score is not None else 0.0
            results.append(
                SearchResult(
                    message_id=message_id,
                    content=content,
                    score=score,
                    metadata=metadata,
                )
            )

        return results


__all__ = ["QdrantSearch"]