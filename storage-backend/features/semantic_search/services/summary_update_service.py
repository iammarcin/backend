"""Detect and regenerate stale session summaries."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from sqlalchemy import and_, select

from features.chat.repositories.chat_sessions import ChatSessionRepository
from features.chat.repositories.chat_messages import ChatMessageRepository
from features.semantic_search.db_models import SessionSummary
from features.semantic_search.repositories import SessionSummaryRepository
from features.semantic_search.services.session_indexing_service import SessionIndexingService
from features.semantic_search.services.session_summary_service import SessionSummaryService

logger = logging.getLogger(__name__)


class SummaryUpdateService:
    """Coordinates stale summary detection and regeneration."""

    def __init__(
        self,
        *,
        summary_repo: SessionSummaryRepository,
        session_repo: ChatSessionRepository,
        message_repo: ChatMessageRepository,
        summary_service: SessionSummaryService,
        indexing_service: SessionIndexingService,
    ) -> None:
        self.summary_repo = summary_repo
        self.session_repo = session_repo
        self.message_repo = message_repo
        self.summary_service = summary_service
        self.indexing_service = indexing_service

    def _current_config_version(self) -> int:
        config_path = Path("config/semantic_search/session_summary.yaml")
        if not config_path.exists():
            return 1
        with config_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        return int(data["versioning"]["config_version"])

    async def find_stale_summaries(
        self,
        *,
        customer_id: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[str]:
        """Return session IDs that need regeneration."""

        stale_sessions = await self.summary_repo.get_stale_summaries(
            customer_id=customer_id,
            limit=limit,
        )
        session_ids = [session_id for session_id, _ in stale_sessions]

        current_version = self._current_config_version()
        stmt = select(SessionSummary.session_id).where(
            SessionSummary.summary_config_version < current_version
        )
        if customer_id is not None:
            stmt = stmt.where(SessionSummary.customer_id == customer_id)
        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self.summary_repo.db.execute(stmt)
        version_stale = list(result.scalars())
        session_ids.extend(version_stale)

        unique_ids = list(dict.fromkeys(session_ids))
        if limit is not None:
            return unique_ids[:limit]
        return unique_ids

    async def regenerate_summary(self, session_id: str) -> Dict[str, Any]:
        """Regenerate a single session summary and reindex."""

        session = await self.session_repo.get_by_id(session_id)
        if session is None:
            return {"session_id": session_id, "success": False, "error": "Session not found"}

        try:
            summary_data = await self.summary_service.generate_summary_for_session(
                session_id=session_id,
                customer_id=session.customer_id,
            )
            await self.indexing_service.index_session(session_id)
            return {"session_id": session_id, "success": True, "summary": summary_data}
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Failed to regenerate session %s: %s", session_id, exc)
            return {"session_id": session_id, "success": False, "error": str(exc)}

    async def regenerate_batch(self, session_ids: List[str], batch_size: int = 10) -> Dict[str, int]:
        regenerated = 0
        failed = 0
        for idx in range(0, len(session_ids), batch_size):
            batch = session_ids[idx : idx + batch_size]
            tasks = [self.regenerate_summary(session_id) for session_id in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    failed += 1
                elif result.get("success"):
                    regenerated += 1
                else:
                    failed += 1
        return {"regenerated": regenerated, "failed": failed}

    async def auto_update_stale(
        self,
        *,
        customer_id: Optional[int] = None,
        limit: Optional[int] = None,
        batch_size: int = 10,
    ) -> Dict[str, int]:
        stale_ids = await self.find_stale_summaries(customer_id=customer_id, limit=limit)
        if not stale_ids:
            return {"found": 0, "regenerated": 0, "failed": 0}

        result = await self.regenerate_batch(stale_ids, batch_size=batch_size)
        return {"found": len(stale_ids), **result}


__all__ = ["SummaryUpdateService"]
