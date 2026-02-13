"""Base utilities shared across semantic search service mixins."""

from __future__ import annotations

import logging

from config.semantic_search import defaults as semantic_defaults
from config.semantic_search.qdrant import COLLECTION_NAME as QDRANT_COLLECTION_NAME
from core import providers as _core_providers  # noqa: F401 - ensure providers registered
from core.providers.semantic.factory import get_semantic_provider
from core.providers.semantic.schemas import SearchRequest
from features.semantic_search.utils.context_formatter import ContextFormatter
from features.semantic_search.utils.metadata_builder import MetadataBuilder

logger = logging.getLogger(__name__)


class SemanticSearchBase:
    """Base object wiring provider, formatters and shared helpers."""

    def __init__(self) -> None:
        self.provider = get_semantic_provider()
        self.context_formatter = ContextFormatter(
            max_tokens=semantic_defaults.CONTEXT_MAX_TOKENS
        )
        self.metadata_builder = MetadataBuilder()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize service (create collection if needed)."""
        if self._initialized:
            return

        try:
            await self.provider.create_collection()
            health = await self.provider.health_check()

            if health.get("healthy"):
                logger.info("Semantic search service initialized successfully")
                self._initialized = True
            else:
                logger.error("Semantic search provider health check failed")
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Failed to initialize semantic search: %s", exc, exc_info=True)

    def _build_search_request(
        self,
        *,
        query: str,
        customer_id: int,
        limit: int | None = None,
        score_threshold: float | None = None,
        search_mode: str = "hybrid",
        collection_name: str = "",
        tags: list[str] | None = None,
        date_range: tuple[str, str] | None = None,
        message_type: str | None = None,
        session_ids: list[str | int] | None = None,
    ) -> SearchRequest:
        """Build SearchRequest object with defaults."""
        normalised_tags = self.metadata_builder.normalize_tags(tags)
        return SearchRequest(
            query=query,
            customer_id=customer_id,
            limit=limit or semantic_defaults.DEFAULT_LIMIT,
            score_threshold=score_threshold or semantic_defaults.DEFAULT_SCORE_THRESHOLD,
            search_mode=search_mode,
            filters=self.metadata_builder.build_search_filters(
                customer_id=customer_id,
                tags=normalised_tags,
                date_range=date_range,
                message_type=message_type,
                session_ids=session_ids,
            ),
            tags=normalised_tags,
            date_range=date_range,
            message_type=message_type,
            session_ids=session_ids,
            collection_name=collection_name or QDRANT_COLLECTION_NAME,
        )
