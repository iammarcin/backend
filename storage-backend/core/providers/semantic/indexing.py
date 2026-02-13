"""Indexing operations for multi-collection semantic provider."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Iterable

from qdrant_client import models
from qdrant_client.models import Distance, PayloadSchemaType, PointIdsList, VectorParams

from config.semantic_search.utils import get_collection_for_mode
from core.exceptions import ProviderError

from .qdrant_indexing import compute_content_hash, content_hash_exists

logger = logging.getLogger(__name__)


class MultiCollectionIndexing:
    """Indexing operations for multi-collection semantic provider."""

    def __init__(self, primary_provider, client, embedding_provider, sparse_provider, circuit_breaker, hybrid_collection, semantic_collection):
        self.primary_provider = primary_provider
        self.client = client
        self.embedding_provider = embedding_provider
        self.sparse_provider = sparse_provider
        self.circuit_breaker = circuit_breaker
        self.hybrid_collection = hybrid_collection
        self.semantic_collection = semantic_collection

    async def index(self, message_id: int, content: str, metadata: dict[str, Any]) -> None:
        if self.circuit_breaker and not self.circuit_breaker.can_attempt():
            logger.warning("Circuit breaker open - skipping dual index")
            return

        metadata_payload = dict(metadata)
        content_hash = compute_content_hash(content)
        customer_id = metadata_payload.get("customer_id")

        if await content_hash_exists(self.primary_provider, content_hash, customer_id):
            logger.info(
                "Skipping duplicate content during dual index",
                extra={"message_id": message_id, "content_hash": content_hash[:16]},
            )
            return

        metadata_payload["content_hash"] = content_hash

        try:
            dense_vector = await self.embedding_provider.generate(content)
            sparse_vector = self.sparse_provider.generate(content)

            await self._run_parallel(
                [
                    self._upsert_semantic(message_id, content, metadata_payload, dense_vector),
                    self._upsert_hybrid(
                        message_id,
                        content,
                        metadata_payload,
                        dense_vector,
                        sparse_vector,
                    ),
                ]
            )
        except Exception as exc:  # pragma: no cover - defensive
            if self.circuit_breaker:
                self.circuit_breaker.record_failure()
            raise ProviderError(f"Dual index operation failed: {exc}") from exc

        if self.circuit_breaker:
            self.circuit_breaker.record_success()

    async def bulk_index(
        self,
        messages: list[tuple[int, str, dict[str, Any]]],
        batch_size: int = 100,
    ) -> None:
        if not messages:
            return

        if self.circuit_breaker and not self.circuit_breaker.can_attempt():
            logger.warning("Circuit breaker open - skipping bulk dual index")
            return

        unique_items: list[tuple[int, str, dict[str, Any]]] = []
        seen_hashes: dict[int | None, set[str]] = {}

        for message_id, content, metadata in messages:
            metadata_payload = dict(metadata)
            customer_id = metadata_payload.get("customer_id")
            customer_hashes = seen_hashes.setdefault(customer_id, set())

            content_hash = compute_content_hash(content)
            if content_hash in customer_hashes:
                logger.debug(
                    "Skipping batch-local duplicate",
                    extra={"message_id": message_id, "content_hash": content_hash[:16]},
                )
                continue

            if await content_hash_exists(self.primary_provider, content_hash, customer_id):
                logger.info(
                    "Skipping existing duplicate during bulk dual index",
                    extra={"message_id": message_id, "content_hash": content_hash[:16]},
                )
                continue

            customer_hashes.add(content_hash)
            metadata_payload["content_hash"] = content_hash
            unique_items.append((message_id, content, metadata_payload))

        if not unique_items:
            logger.info("No unique messages to bulk dual index")
            return

        texts = [content for _, content, _ in unique_items]

        try:
            embeddings = await self.embedding_provider.generate_batch(texts, batch_size=batch_size)

            total = len(unique_items)
            for start in range(0, total, batch_size):
                batch = unique_items[start : start + batch_size]
                dense_vectors = embeddings[start : start + len(batch)]
                sparse_vectors = [
                    self.sparse_provider.generate(content) for _, content, _ in batch
                ]

                await self._run_parallel(
                    [
                        self._bulk_upsert(
                            collection_name=self.semantic_collection,
                            batch=batch,
                            dense_vectors=dense_vectors,
                            sparse_vectors=None,
                        ),
                        self._bulk_upsert(
                            collection_name=self.hybrid_collection,
                            batch=batch,
                            dense_vectors=dense_vectors,
                            sparse_vectors=sparse_vectors,
                        ),
                    ]
                )
        except Exception as exc:  # pragma: no cover - defensive
            if self.circuit_breaker:
                self.circuit_breaker.record_failure()
            raise ProviderError(f"Bulk dual index failed: {exc}") from exc

        if self.circuit_breaker:
            self.circuit_breaker.record_success()

    async def update(self, message_id: int, content: str, metadata: dict[str, Any]) -> None:
        await self.index(message_id, content, metadata)

    async def delete(self, message_id: int) -> None:
        await self._run_parallel(
            [
                self.client.delete(
                    collection_name=self.semantic_collection,
                    points_selector=PointIdsList(points=[message_id]),
                ),
                self.client.delete(
                    collection_name=self.hybrid_collection,
                    points_selector=PointIdsList(points=[message_id]),
                ),
            ]
        )

    async def _upsert_semantic(
        self,
        message_id: int,
        content: str,
        metadata: dict[str, Any],
        dense_vector: list[float],
    ) -> None:
        point = models.PointStruct(
            id=message_id,
            payload={"content": content, **metadata},
            vector={"dense": dense_vector},
        )
        await self.client.upsert(
            collection_name=self.semantic_collection,
            points=[point],
        )

    async def _upsert_hybrid(
        self,
        message_id: int,
        content: str,
        metadata: dict[str, Any],
        dense_vector: list[float],
        sparse_vector: dict[str, Any],
    ) -> None:
        point = models.PointStruct(
            id=message_id,
            payload={"content": content, **metadata},
            vector={
                "dense": dense_vector,
                "sparse": models.SparseVector(
                    indices=sparse_vector["indices"],
                    values=sparse_vector["values"],
                ),
            },
        )
        await self.client.upsert(
            collection_name=self.hybrid_collection,
            points=[point],
        )

    async def _bulk_upsert(
        self,
        *,
        collection_name: str,
        batch: list[tuple[int, str, dict[str, Any]]],
        dense_vectors: list[list[float]],
        sparse_vectors: list[dict[str, Any]] | None,
    ) -> None:
        points: list[models.PointStruct] = []
        for idx, ((message_id, content, metadata), dense_vector) in enumerate(
            zip(batch, dense_vectors)
        ):
            payload = {"content": content, **metadata}
            vector: dict[str, Any] = {"dense": dense_vector}

            if sparse_vectors is not None:
                sparse_vector = sparse_vectors[idx]
                vector["sparse"] = models.SparseVector(
                    indices=sparse_vector["indices"],
                    values=sparse_vector["values"],
                )

            points.append(
                models.PointStruct(
                    id=message_id,
                    payload=payload,
                    vector=vector,
                )
            )

        await self.client.upsert(collection_name=collection_name, points=points)

    async def _run_parallel(self, tasks: Iterable[asyncio.Future]) -> None:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        errors = [result for result in results if isinstance(result, Exception)]
        if errors:
            error = errors[0]
            logger.error("Dual collection operation failed: %s", error)
            raise ProviderError(f"Dual collection operation failed: {error}") from error

    async def ensure_semantic_collection(self) -> None:
        collections = await self.client.get_collections()
        existing = {collection.name for collection in collections.collections}
        if self.semantic_collection in existing:
            return

        await self.client.create_collection(
            collection_name=self.semantic_collection,
            vectors_config={
                "dense": VectorParams(
                    size=self.embedding_provider.dimensions,
                    distance=Distance.COSINE,
                ),
            },
        )
        await self._create_payload_indexes(self.semantic_collection)

    async def _create_payload_indexes(self, collection_name: str) -> None:
        indexes = [
            ("customer_id", PayloadSchemaType.INTEGER),
            ("tags", PayloadSchemaType.KEYWORD),
            ("created_at", PayloadSchemaType.DATETIME),
            ("message_type", PayloadSchemaType.KEYWORD),
            ("content_hash", PayloadSchemaType.KEYWORD),
        ]

        for field_name, field_schema in indexes:
            try:
                await self.client.create_payload_index(
                    collection_name=collection_name,
                    field_name=field_name,
                    field_schema=field_schema,
                )
            except Exception:  # pragma: no cover - index may already exist
                logger.debug(
                    "Payload index already exists",
                    extra={"collection": collection_name, "field": field_name},
                )


__all__ = ["MultiCollectionIndexing"]
