"""Index session summaries in Qdrant."""

from __future__ import annotations

import hashlib
import logging
import json
from typing import Iterable, List, Sequence

from qdrant_client import AsyncQdrantClient, models
from qdrant_client.models import PointIdsList, PointStruct, SparseVector

from config.semantic_search.qdrant import QDRANT_COLLECTION_NAME_SESSIONS
from core.clients.ai import ai_clients, get_openai_async_client
from core.config import settings
from core.exceptions import ProviderError
from core.providers.semantic.embeddings import OpenAIEmbeddingProvider
from features.semantic_search.repositories import SessionSummaryRepository

logger = logging.getLogger(__name__)

COLLECTION_NAME = QDRANT_COLLECTION_NAME_SESSIONS


class SessionIndexingService:
    """Service responsible for syncing summaries into Qdrant."""

    def __init__(
        self,
        summary_repo: SessionSummaryRepository,
        *,
        qdrant_client: AsyncQdrantClient | None = None,
        embedding_provider: OpenAIEmbeddingProvider | None = None,
    ) -> None:
        self.summary_repo = summary_repo
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
        """Release Qdrant client resources."""

        if self._owns_client:
            await self.qdrant_client.close()

    async def _generate_embedding(self, text: str) -> List[float]:
        try:
            return await self.embedding_provider.generate(text)
        except Exception as exc:  # pragma: no cover - network failures
            raise ProviderError(f"Failed to generate embedding: {exc}") from exc

    def _generate_sparse_vector(self, summary: str, topics: Sequence[str], entities: Sequence[str]) -> SparseVector:
        combined = f"{summary} {' '.join(topics)} {' '.join(entities)}"
        tokens = combined.lower().split()
        counts: dict[str, int] = {}

        for token in tokens:
            if len(token) <= 2:
                continue
            counts[token] = counts.get(token, 0) + 1

        buckets: dict[int, float] = {}

        for token, count in counts.items():
            hashed = int(hashlib.md5(token.encode()).hexdigest()[:8], 16)
            bucket = hashed % 100000
            buckets[bucket] = buckets.get(bucket, 0.0) + float(count)

        indices = list(buckets.keys())
        values = [buckets[idx] for idx in indices]

        return SparseVector(indices=indices, values=values)

    def _point_id(self, session_id: str) -> str:
        return session_id

    async def index_session(self, session_id: str) -> bool:
        """Index a single session summary into Qdrant."""

        summary = await self.summary_repo.get_by_session_id(session_id)
        if summary is None:
            logger.warning("No summary found for session %s", session_id)
            return False

        dense_vector = await self._generate_embedding(summary.summary)
        key_topics = self._normalize_sequence(summary.key_topics)
        entities = self._normalize_sequence(summary.main_entities)
        tags = self._normalize_sequence(summary.tags)

        sparse_vector = self._generate_sparse_vector(
            summary.summary,
            key_topics,
            entities,
        )

        def to_iso_string(date_value):
            if date_value is None:
                return None
            if isinstance(date_value, str):
                return date_value
            return date_value.isoformat()

        payload = {
            "session_id": summary.session_id,
            "customer_id": summary.customer_id,
            "summary": summary.summary,
            "key_topics": key_topics,
            "main_entities": entities,
            "message_count": summary.message_count,
            "first_message_date": to_iso_string(summary.first_message_date),
            "last_message_date": to_iso_string(summary.last_message_date),
            "tags": tags,
            "summary_model": summary.summary_model,
            "generated_at": to_iso_string(summary.generated_at),
            "last_updated": to_iso_string(summary.last_updated),
        }

        point_id = self._point_id(summary.session_id)
        point = PointStruct(
            id=point_id,
            vector={
                "dense": dense_vector,
                "sparse": sparse_vector,
            },
            payload=payload,
        )

        try:
            await self.qdrant_client.upsert(
                collection_name=COLLECTION_NAME,
                points=[point],
            )
            logger.info("Indexed session %s (point_id=%s)", session_id, point_id)
            return True
        except Exception as exc:  # pragma: no cover - network failure
            logger.error("Failed to index session %s: %s", session_id, exc)
            raise ProviderError(f"Indexing failed: {exc}") from exc

    @staticmethod
    def _normalize_sequence(value: Sequence[str] | str | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except json.JSONDecodeError:
                pass
            return [text]
        return list(value)

    async def index_sessions_batch(self, session_ids: Iterable[str]) -> dict[str, int]:
        indexed = 0
        failed = 0

        for session_id in session_ids:
            try:
                success = await self.index_session(session_id)
                if success:
                    indexed += 1
                else:
                    failed += 1
            except ProviderError as exc:
                logger.error("Provider error while indexing %s: %s", session_id, exc)
                failed += 1

        return {"indexed": indexed, "failed": failed}

    async def delete_session(self, customer_id: int, session_id: str) -> bool:
        """Remove a session summary from Qdrant."""

        point_id = self._point_id(session_id)
        try:
            await self.qdrant_client.delete(
                collection_name=COLLECTION_NAME,
                points_selector=PointIdsList(points=[point_id]),
            )
            logger.info("Deleted session %s from index", session_id)
            return True
        except Exception as exc:
            logger.error("Failed to delete session %s: %s", session_id, exc)
            return False
