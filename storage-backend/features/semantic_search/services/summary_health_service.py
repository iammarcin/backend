"""Summary health metrics service."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy import func, select

from features.chat.db_models import ChatSession
from features.semantic_search.db_models import SessionSummary
from features.semantic_search.repositories import SessionSummaryRepository

logger = logging.getLogger(__name__)


class SummaryHealthService:
    """Compute coverage and freshness metrics for summaries."""

    def __init__(self, summary_repo: SessionSummaryRepository) -> None:
        self.summary_repo = summary_repo

    async def get_metrics(self, customer_id: Optional[int] = None) -> Dict[str, Any]:
        db = self.summary_repo.db

        stmt = select(func.count(SessionSummary.id))
        if customer_id is not None:
            stmt = stmt.where(SessionSummary.customer_id == customer_id)
        total_summaries = (await db.execute(stmt)).scalar() or 0

        stmt = select(func.count(ChatSession.session_id))
        if customer_id is not None:
            stmt = stmt.where(ChatSession.customer_id == customer_id)
        total_sessions = (await db.execute(stmt)).scalar() or 0

        cutoff = datetime.utcnow() - timedelta(days=1)
        stmt = select(func.count(SessionSummary.id)).where(SessionSummary.last_updated < cutoff)
        if customer_id is not None:
            stmt = stmt.where(SessionSummary.customer_id == customer_id)
        stale_summaries = (await db.execute(stmt)).scalar() or 0

        coverage = (total_summaries / total_sessions * 100) if total_sessions else 0.0
        stale_percent = (stale_summaries / total_summaries * 100) if total_summaries else 0.0

        return {
            "total_summaries": total_summaries,
            "total_sessions": total_sessions,
            "coverage_percent": round(coverage, 2),
            "stale_summaries": stale_summaries,
            "stale_percent": round(stale_percent, 2),
        }


__all__ = ["SummaryHealthService"]
