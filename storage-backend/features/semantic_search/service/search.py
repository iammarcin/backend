"""Search related mixins for the semantic search service."""

from __future__ import annotations

import asyncio
import logging

from typing import TYPE_CHECKING

from config.semantic_search import defaults as semantic_defaults
from config.semantic_search.utils import get_collection_for_mode
from core.config import DEBUG_MODE
from core.providers.semantic.schemas import SearchResult

if TYPE_CHECKING:
    from .base import SemanticSearchBase
    from core.streaming.manager import StreamingManager

logger = logging.getLogger(__name__)


class SemanticSearchQueryMixin:
    """Provides search and context formatting operations."""

    async def search(
        self: "SemanticSearchBase",
        query: str,
        customer_id: int,
        limit: int | None = None,
        score_threshold: float | None = None,
        search_mode: str = "hybrid",
        tags: list[str] | None = None,
        date_range: tuple[str, str] | None = None,
        message_type: str | None = None,
        session_ids: list[str | int] | None = None,
    ) -> list[SearchResult]:
        """Perform semantic search and return raw results.

        This method is used by diagnostic/explorer tools that need access to
        raw search results with scores. For LLM context enhancement, use
        search_and_format_context() instead.
        """
        try:
            collection_name = get_collection_for_mode(search_mode)
            request = self._build_search_request(
                query=query,
                customer_id=customer_id,
                limit=limit,
                score_threshold=score_threshold,
                search_mode=search_mode,
                collection_name=collection_name,
                tags=tags,
                date_range=date_range,
                message_type=message_type,
                session_ids=session_ids,
            )

            results = await asyncio.wait_for(
                self.provider.search(request),
                timeout=semantic_defaults.TOTAL_TIMEOUT,
            )

            logger.info(
                "Semantic search for customer %s returned %s results (mode=%s, collection=%s)",
                customer_id,
                len(results),
                search_mode,
                collection_name,
            )

            return results

        except asyncio.TimeoutError:
            logger.error(
                "Semantic search timeout after %ss",
                semantic_defaults.TOTAL_TIMEOUT,
            )
            return []
        except Exception as exc:
            logger.error(
                "Semantic search failed for customer %s: %s",
                customer_id,
                exc,
                exc_info=True,
            )
            return []

    async def search_and_format_context(
        self: "SemanticSearchBase",
        query: str,
        customer_id: int,
        limit: int | None = None,
        score_threshold: float | None = None,
        search_mode: str = "hybrid",
        tags: list[str] | None = None,
        date_range: tuple[str, str] | None = None,
        message_type: str | None = None,
        session_ids: list[str | int] | None = None,
        manager: "StreamingManager | None" = None,
    ) -> str:
        """Perform semantic search and format results as LLM context."""
        try:
            return await asyncio.wait_for(
                self._search_and_format_internal(
                    query=query,
                    customer_id=customer_id,
                    limit=limit,
                    score_threshold=score_threshold,
                    search_mode=search_mode,
                    tags=tags,
                    date_range=date_range,
                    message_type=message_type,
                    session_ids=session_ids,
                    manager=manager,
                ),
                timeout=semantic_defaults.TOTAL_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.error(
                "Semantic search total timeout after %ss",
                semantic_defaults.TOTAL_TIMEOUT,
            )
            return ""
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error(
                "Semantic search failed for customer %s: %s", customer_id, exc, exc_info=True
            )
            return ""

    async def _search_and_format_internal(
        self: "SemanticSearchBase",
        *,
        query: str,
        customer_id: int,
        limit: int | None,
        score_threshold: float | None,
        search_mode: str,
        tags: list[str] | None,
        date_range: tuple[str, str] | None,
        message_type: str | None,
        session_ids: list[str | int] | None,
        manager: "StreamingManager | None",
    ) -> str:
        """Perform semantic search without outer timeout handling."""

        collection_name = get_collection_for_mode(search_mode)

        request = self._build_search_request(
            query=query,
            customer_id=customer_id,
            limit=limit,
            score_threshold=score_threshold,
            search_mode=search_mode,
            collection_name=collection_name,
            tags=tags,
            date_range=date_range,
            message_type=message_type,
            session_ids=session_ids,
        )

        results = await self.provider.search(request)

        if not results:
            logger.info("No semantic search results for customer %s", customer_id)
            return ""

        # Log top scores for debugging (RRF scores are rank-based: 0.5, 0.33, 0.25...)
        top_scores = [f"{r.score:.3f}" for r in results[:5]]
        logger.info(
            "Semantic search returned %s results, top scores: [%s]",
            len(results),
            ", ".join(top_scores),
        )

        await self._emit_top_scores_event(
            manager=manager,
            result_count=len(results),
            top_scores=top_scores,
            search_mode=search_mode,
            collection_name=collection_name,
        )

        context = self.context_formatter.format_results(
            results=results,
            original_query=query,
            include_scores=DEBUG_MODE,
        )

        logger.info(
            "Formatted semantic context: %s results, %s tokens",
            len(results),
            self.context_formatter.token_counter.count_tokens(context),
        )

        return context

    async def _emit_top_scores_event(
        self: "SemanticSearchBase",
        *,
        manager: "StreamingManager | None",
        result_count: int,
        top_scores: list[str],
        search_mode: str,
        collection_name: str,
    ) -> None:
        """Emit websocket event with semantic search scores."""
        if not manager:
            return

        event_payload = {
            "type": "semanticSearchScores",
            "result_count": result_count,
            "top_scores": top_scores,
            "mode": search_mode,
            "collection": collection_name,
        }

        try:
            await manager.send_to_queues(
                {
                    "type": "custom_event",
                    "event_type": "semanticSearchScores",
                    "content": event_payload,
                }
            )
        except Exception:
            logger.warning("Failed to send semantic search scores event", exc_info=True)
