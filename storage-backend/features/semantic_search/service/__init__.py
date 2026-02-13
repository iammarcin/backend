"""Semantic search service exposing a cohesive public interface."""

from __future__ import annotations

from config.semantic_search import defaults as semantic_defaults
from config.semantic_search.qdrant import URL as QDRANT_URL
from config.api_keys import OPENAI_API_KEY
from core.config import settings
from core.exceptions import ConfigurationError

from features.semantic_search.schemas import SemanticSearchMode
from features.semantic_search.services.multi_tier_search_service import (
    MultiTierSearchConfig,
    MultiTierSearchService,
)
from features.semantic_search.services.session_search_service import SessionSearchService

from .base import SemanticSearchBase
from .bulk import SemanticSearchBulkMixin
from .indexing import SemanticSearchIndexingMixin
from .search import SemanticSearchQueryMixin


class SemanticSearchService(
    SemanticSearchQueryMixin,
    SemanticSearchIndexingMixin,
    SemanticSearchBulkMixin,
    SemanticSearchBase,
):
    """High-level service for semantic search operations."""

    def __init__(self) -> None:  # pragma: no cover - simple wiring
        super().__init__()
        self.session_search_service = SessionSearchService()
        self.multi_tier_service = MultiTierSearchService(
            session_search_service=self.session_search_service,
            message_search_service=self,
        )
        self._session_modes = {
            SemanticSearchMode.SESSION_SEMANTIC,
            SemanticSearchMode.SESSION_HYBRID,
        }

    def _parse_mode(self, mode: str | None) -> SemanticSearchMode:
        try:
            return SemanticSearchMode(mode or semantic_defaults.DEFAULT_SEARCH_MODE)
        except ValueError:
            return SemanticSearchMode(semantic_defaults.DEFAULT_SEARCH_MODE)

    async def search(
        self,
        query: str,
        customer_id: int,
        limit: int | None = None,
        score_threshold: float | None = None,
        search_mode: str = "hybrid",
        tags: list[str] | None = None,
        date_range: tuple[str, str] | None = None,
        message_type: str | None = None,
        session_ids: list[str | int] | None = None,
        top_sessions: int | None = None,
        messages_per_session: int | None = None,
    ):
        """Route searches to session or message providers."""

        semantic_mode = self._parse_mode(search_mode)
        if semantic_mode == SemanticSearchMode.MULTI_TIER:
            config = MultiTierSearchConfig(
                top_sessions=top_sessions or semantic_defaults.MULTI_TIER_TOP_SESSIONS,
                messages_per_session=messages_per_session
                or semantic_defaults.MULTI_TIER_MESSAGES_PER_SESSION,
            )
            results = await self.multi_tier_service.search(
                query=query,
                customer_id=customer_id,
                config=config,
            )
            return [result.to_dict() for result in results]

        if semantic_mode in self._session_modes:
            return await self.session_search_service.search(
                query=query,
                customer_id=customer_id,
                search_mode=semantic_mode,
                limit=limit or semantic_defaults.DEFAULT_LIMIT,
            )

        return await SemanticSearchQueryMixin.search(
            self,
            query=query,
            customer_id=customer_id,
            limit=limit,
            score_threshold=score_threshold,
            search_mode=semantic_mode.value,
            tags=tags,
            date_range=date_range,
            message_type=message_type,
            session_ids=session_ids,
        )

    async def search_and_format_context(
        self,
        query: str,
        customer_id: int,
        limit: int | None = None,
        score_threshold: float | None = None,
        search_mode: str = "hybrid",
        tags: list[str] | None = None,
        date_range: tuple[str, str] | None = None,
        message_type: str | None = None,
        session_ids: list[str | int] | None = None,
        manager=None,
        top_sessions: int | None = None,
        messages_per_session: int | None = None,
    ) -> str:
        semantic_mode = self._parse_mode(search_mode)
        if semantic_mode == SemanticSearchMode.MULTI_TIER:
            config = MultiTierSearchConfig(
                top_sessions=top_sessions or semantic_defaults.MULTI_TIER_TOP_SESSIONS,
                messages_per_session=messages_per_session
                or semantic_defaults.MULTI_TIER_MESSAGES_PER_SESSION,
            )
            multi_results = await self.multi_tier_service.search(
                query=query,
                customer_id=customer_id,
                config=config,
            )
            return self.context_formatter.format_multi_tier_results(
                results=[result.to_dict() for result in multi_results],
                original_query=query,
            )

        if semantic_mode in self._session_modes:
            results = await self.session_search_service.search(
                query=query,
                customer_id=customer_id,
                search_mode=semantic_mode,
                limit=limit or semantic_defaults.DEFAULT_LIMIT,
            )
            return self.context_formatter.format_session_results(
                results=results,
                original_query=query,
            )

        return await SemanticSearchQueryMixin.search_and_format_context(
            self,
            query=query,
            customer_id=customer_id,
            limit=limit,
            score_threshold=score_threshold,
            search_mode=semantic_mode.value,
            tags=tags,
            date_range=date_range,
            message_type=message_type,
            session_ids=session_ids,
            manager=manager,
        )


_service_instance: SemanticSearchService | None = None


def _validate_semantic_search_configuration() -> None:
    """Ensure required configuration is present before creating the service."""

    if not settings.semantic_search_enabled:
        raise ConfigurationError(
            "Semantic search requested but disabled via settings.",
            key="SEMANTIC_SEARCH_ENABLED",
        )

    if not OPENAI_API_KEY:
        raise ConfigurationError(
            "OPENAI_API_KEY is required for semantic search.",
            key="OPENAI_API_KEY",
        )

    if not QDRANT_URL:
        raise ConfigurationError(
            "QDRANT_URL is required for semantic search.",
            key="QDRANT_URL",
        )


def get_semantic_search_service() -> "SemanticSearchService":
    """Get or create singleton service instance."""
    global _service_instance
    if _service_instance is None:
        _validate_semantic_search_configuration()
        _service_instance = SemanticSearchService()
    return _service_instance


# Re-export settings for test compatibility

__all__ = ["SemanticSearchService", "get_semantic_search_service"]
