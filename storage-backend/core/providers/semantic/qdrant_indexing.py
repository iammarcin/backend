"""Indexing helpers for the Qdrant semantic provider."""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Iterable, Tuple, TYPE_CHECKING

from qdrant_client import models
from qdrant_client.models import PointIdsList, PointStruct

from core.exceptions import ProviderError

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .qdrant import QdrantSemanticProvider

logger = logging.getLogger(__name__)


def compute_content_hash(content: str) -> str:
    """Return deterministic hash for message content."""
    return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()


async def content_hash_exists(
    provider: "QdrantSemanticProvider",
    content_hash: str,
    customer_id: int | None,
) -> bool:
    """Check if hash already exists for customer."""
    must_conditions = [
        models.FieldCondition(
            key="content_hash",
            match=models.MatchValue(value=content_hash),
        )
    ]

    if customer_id is not None:
        must_conditions.append(
            models.FieldCondition(
                key="customer_id",
                match=models.MatchValue(value=customer_id),
            )
        )

    try:
        points, _ = await provider.client.scroll(
            collection_name=provider.collection_name,
            limit=1,
            with_payload=False,
            scroll_filter=models.Filter(must=must_conditions),
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to check duplicate content hash: %s", exc)
        return False

    return len(points) > 0

async def index_message(
    provider: "QdrantSemanticProvider",
    message_id: int,
    content: str,
    metadata: dict[str, Any],
) -> None:
    """Index message with both dense and sparse vectors."""

    metadata_payload = dict(metadata)
    content_hash = compute_content_hash(content)
    customer_id = metadata_payload.get("customer_id")

    if await content_hash_exists(provider, content_hash, customer_id):
        logger.info(
            "Skipping duplicate content",
            extra={
                "message_id": message_id,
                "content_hash": content_hash[:16],
                "customer_id": customer_id,
            },
        )
        return

    metadata_payload["content_hash"] = content_hash

    # Generate dense vector (existing)
    dense_vector = await provider.embedding_provider.generate(content)

    # Generate sparse vector (new)
    sparse_vector = provider.sparse_provider.generate(content)

    point = PointStruct(
        id=message_id,
        payload={"content": content, **metadata_payload},
        vector={
            "dense": dense_vector,
            "sparse": models.SparseVector(
                indices=sparse_vector["indices"],
                values=sparse_vector["values"],
            ),
        },
    )

    try:
        await provider.client.upsert(
            collection_name=provider.collection_name,
            points=[point],
        )
    except Exception as exc:
        provider.circuit_breaker.record_failure()
        raise ProviderError(f"Index operation failed: {exc}") from exc

    provider.circuit_breaker.record_success()

    logger.debug(
        f"Indexed message {message_id} with dense + sparse vectors",
        extra={
            "dense_dims": len(dense_vector),
            "sparse_terms": len(sparse_vector["indices"]),
        },
    )


async def bulk_index(
    provider: "QdrantSemanticProvider",
    messages: Iterable[Tuple[int, str, dict[str, Any]]],
    *,
    batch_size: int = 100,
) -> None:
    items_raw = list(messages)
    if not items_raw:
        return

    if not provider.circuit_breaker.can_attempt():
        provider.logger.warning("Circuit breaker open - skipping bulk index")
        return

    unique_items: list[Tuple[int, str, dict[str, Any]]] = []
    seen_hashes: dict[int | None, set[str]] = {}

    for message_id, content, metadata in items_raw:
        metadata_payload = dict(metadata)
        customer_id = metadata_payload.get("customer_id")
        customer_hashes = seen_hashes.setdefault(customer_id, set())

        content_hash = compute_content_hash(content)
        if content_hash in customer_hashes:
            provider.logger.debug(
                "Skipping batch duplicate",
                extra={"message_id": message_id, "content_hash": content_hash[:16]},
            )
            continue

        already_exists = await content_hash_exists(provider, content_hash, customer_id)
        if already_exists:
            provider.logger.info(
                "Skipping existing duplicate",
                extra={"message_id": message_id, "content_hash": content_hash[:16]},
            )
            continue

        customer_hashes.add(content_hash)
        metadata_payload["content_hash"] = content_hash
        unique_items.append((message_id, content, metadata_payload))

    if not unique_items:
        provider.logger.info("Bulk index: no unique items to index")
        return

    provider.logger.info(
        "Bulk index: %s submitted, %s unique after deduplication",
        len(items_raw),
        len(unique_items),
    )

    texts = [content for _, content, _ in unique_items]

    try:
        embeddings = await provider.embedding_provider.generate_batch(texts, batch_size=batch_size)
    except Exception as exc:
        provider.circuit_breaker.record_failure()
        raise ProviderError(f"Bulk embedding generation failed: {exc}") from exc

    try:
        total = len(unique_items)
        for start in range(0, total, batch_size):
            batch_messages = unique_items[start: start + batch_size]
            batch_embeddings = embeddings[start: start + len(batch_messages)]

            # Generate sparse vectors for this batch
            batch_sparse_vectors = [
                provider.sparse_provider.generate(content)
                for _, content, _ in batch_messages
            ]

            points = [
                PointStruct(
                    id=message_id,
                    payload={"content": content, **metadata},
                    vector={
                        "dense": embedding,
                        "sparse": models.SparseVector(
                            indices=sparse_vector["indices"],
                            values=sparse_vector["values"],
                        ),
                    },
                )
                for (message_id, content, metadata), embedding, sparse_vector in zip(
                    batch_messages, batch_embeddings, batch_sparse_vectors
                )
            ]

            await provider.client.upsert(
                collection_name=provider.collection_name,
                points=points,
            )

            provider.logger.debug(
                "Indexed batch with dense + sparse vectors",
                extra={
                    "batch_index": start // batch_size + 1,
                    "batch_size": len(points),
                    "processed": start + len(points),
                    "total": total,
                },
            )
    except Exception as exc:
        provider.circuit_breaker.record_failure()
        raise ProviderError(f"Bulk index operation failed: {exc}") from exc

    provider.circuit_breaker.record_success()


async def delete_message(provider: "QdrantSemanticProvider", message_id: int) -> None:
    if not provider.circuit_breaker.can_attempt():
        provider.logger.warning("Circuit breaker open - skipping delete operation")
        return

    try:
        await provider.client.delete(
            collection_name=provider.collection_name,
            points_selector=PointIdsList(points=[message_id]),
        )
    except Exception as exc:
        provider.circuit_breaker.record_failure()
        raise ProviderError(f"Delete operation failed: {exc}") from exc

    provider.circuit_breaker.record_success()


async def create_collection(provider: "QdrantSemanticProvider") -> None:
    try:
        collections = await provider.client.get_collections()
        existing_names = {collection.name for collection in collections.collections}

        if provider.collection_name in existing_names:
            provider.logger.info(
                "Qdrant collection already exists", extra={"collection": provider.collection_name}
            )
            return

        # Create collection with named vectors for hybrid search (Qdrant 1.16 API)
        # IMPORTANT: Dense and sparse vectors require SEPARATE config parameters
        from qdrant_client.models import (
            VectorParams, Distance, SparseVectorParams,
            SparseIndexParams, OptimizersConfigDiff
        )

        await provider.client.create_collection(
            collection_name=provider.collection_name,
            # Dense vectors config
            vectors_config={
                "dense": VectorParams(
                    size=provider.embedding_provider.dimensions,
                    distance=Distance.COSINE,
                ),
            },
            # Sparse vectors config (SEPARATE parameter!)
            sparse_vectors_config={
                "sparse": SparseVectorParams(
                    index=SparseIndexParams(on_disk=False),
                ),
            },
            optimizers_config=OptimizersConfigDiff(
                indexing_threshold=10000,
            ),
        )

        await provider.create_payload_indexes()
    except Exception as exc:
        provider.circuit_breaker.record_failure()
        raise ProviderError(f"Collection creation failed: {exc}") from exc

    provider.circuit_breaker.record_success()


__all__ = ["index_message", "bulk_index", "delete_message", "create_collection"]
