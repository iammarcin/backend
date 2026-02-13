"""Service wrapper around session-level search provider."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.providers.semantic.session_search_provider import (
    SessionSearchProvider,
    SessionSearchResult,
    SessionSearchType,
)
from features.semantic_search.schemas import SemanticSearchMode


class SessionSearchService:
    """High level helper for executing session searches."""

    def __init__(self, provider: SessionSearchProvider | None = None) -> None:
        self.provider = provider or SessionSearchProvider()

    def _map_mode(self, mode: SemanticSearchMode) -> SessionSearchType:
        mapping = {
            SemanticSearchMode.SESSION_SEMANTIC: SessionSearchType.DENSE,
            SemanticSearchMode.SESSION_HYBRID: SessionSearchType.HYBRID,
        }
        if mode not in mapping:
            raise ValueError(f"Unsupported session search mode: {mode}")
        return mapping[mode]

    async def search(
        self,
        *,
        query: str,
        customer_id: int,
        search_mode: SemanticSearchMode,
        limit: int = 10,
        topics_filter: Optional[List[str]] = None,
        entities_filter: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Execute session search and return serialisable payloads."""

        search_type = self._map_mode(search_mode)
        results: List[SessionSearchResult] = await self.provider.search(
            query=query,
            customer_id=customer_id,
            search_type=search_type,
            limit=limit,
            topics_filter=topics_filter,
            entities_filter=entities_filter,
        )

        return [result.to_dict() for result in results]

    async def close(self) -> None:
        await self.provider.close()
