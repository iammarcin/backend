"""Multi-tier search orchestration service."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence

from config.semantic_search import defaults as semantic_defaults
from features.semantic_search.schemas import SemanticSearchMode
from features.semantic_search.services.session_search_service import SessionSearchService

logger = logging.getLogger(__name__)


@dataclass
class MultiTierSearchConfig:
    """Configuration for multi-tier search."""

    top_sessions: int = semantic_defaults.MULTI_TIER_TOP_SESSIONS
    messages_per_session: int = semantic_defaults.MULTI_TIER_MESSAGES_PER_SESSION
    session_search_mode: SemanticSearchMode = SemanticSearchMode.SESSION_HYBRID
    message_search_mode: SemanticSearchMode = SemanticSearchMode.HYBRID


@dataclass
class MultiTierSearchResult:
    """Represents a session and its matched messages."""

    session_id: str
    session_summary: str
    session_topics: Sequence[str]
    session_entities: Sequence[str]
    session_score: float
    matched_messages: List[Dict[str, Any]]
    session_last_updated: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "session_summary": self.session_summary,
            "session_topics": list(self.session_topics),
            "session_entities": list(self.session_entities),
            "session_score": self.session_score,
            "matched_messages": self.matched_messages,
            "session_last_updated": self.session_last_updated,
        }


class MultiTierSearchService:
    """Executes session → message hierarchical searches."""

    def __init__(
        self,
        session_search_service: SessionSearchService,
        message_search_service: "SemanticSearchService",
    ) -> None:
        self.session_search_service = session_search_service
        self.message_search_service = message_search_service

    async def search(
        self,
        *,
        query: str,
        customer_id: int,
        config: MultiTierSearchConfig,
    ) -> List[MultiTierSearchResult]:
        session_results = await self.session_search_service.search(
            query=query,
            customer_id=customer_id,
            search_mode=config.session_search_mode,
            limit=config.top_sessions * 2,
        )

        if not session_results:
            logger.info("Multi-tier search found no sessions for customer %s", customer_id)
            return []

        selected_sessions = session_results[: config.top_sessions]
        tasks = [
            self._search_messages_in_session(
                query=query,
                customer_id=customer_id,
                session_id=session["session_id"],
                limit=config.messages_per_session,
                search_mode=config.message_search_mode,
            )
            for session in selected_sessions
        ]

        message_batches = await asyncio.gather(*tasks, return_exceptions=True)
        results: list[MultiTierSearchResult] = []

        for session_result, message_result in zip(selected_sessions, message_batches):
            if isinstance(message_result, Exception):
                logger.error(
                    "Message search failed for session %s: %s",
                    session_result["session_id"],
                    message_result,
                )
                matched_messages: list[dict[str, Any]] = []
            else:
                matched_messages = message_result

            results.append(
                MultiTierSearchResult(
                    session_id=session_result["session_id"],
                    session_summary=session_result.get("summary", ""),
                    session_topics=session_result.get("key_topics", []),
                    session_entities=session_result.get("main_entities", []),
                    session_score=float(session_result.get("score", 0.0)),
                    matched_messages=matched_messages,
                    session_last_updated=session_result.get("last_updated"),
                )
            )

        return results

    async def _search_messages_in_session(
        self,
        *,
        query: str,
        customer_id: int,
        session_id: str,
        limit: int,
        search_mode: SemanticSearchMode,
    ) -> List[Dict[str, Any]]:
        raw_results = await self.message_search_service.search(
            query=query,
            customer_id=customer_id,
            limit=limit,
            search_mode=search_mode.value,
            session_ids=[session_id],
        )

        formatted: list[dict[str, Any]] = []
        for result in raw_results:
            metadata = result.metadata if hasattr(result, "metadata") else {}
            formatted.append(
                {
                    "message_id": getattr(result, "message_id", None),
                    "content": getattr(result, "content", ""),
                    "score": getattr(result, "score", 0.0),
                    "role": metadata.get("message_type", metadata.get("role", "assistant")),
                }
            )
        return formatted


__all__ = ["MultiTierSearchConfig", "MultiTierSearchResult", "MultiTierSearchService"]
