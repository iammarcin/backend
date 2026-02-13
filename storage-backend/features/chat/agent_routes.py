"""REST API endpoint for unified agent status."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import AuthContext, require_auth_context
from features.chat.db_models import ChatSession
from features.chat.dependencies import get_chat_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agents", tags=["Agents"])


def compute_agent_status(last_activity: datetime | None) -> str:
    """Derive agent status from the most recent activity timestamp.

    Returns ``'active'`` when *last_activity* is within the last 5 minutes,
    ``'idle'`` otherwise (including when *last_activity* is ``None``).
    """
    if last_activity is None:
        return "idle"
    now = datetime.now(timezone.utc)
    minutes_since = (now - last_activity).total_seconds() / 60
    if minutes_since <= 5:
        return "active"
    return "idle"


class AgentStatusItem(BaseModel):
    """Status and session metrics for a single agent."""

    name: str
    status: str = Field(default="idle")
    session_count: int
    active_task_count: int = Field(default=0)
    last_activity: Optional[str] = Field(default=None)


class AgentStatusResponse(BaseModel):
    """Aggregated status for all agents belonging to a customer."""

    agents: List[AgentStatusItem] = Field(default_factory=list)


@router.get("/status", response_model=AgentStatusResponse)
async def get_agent_status(
    customer_id: int = Query(..., ge=1),
    auth: AuthContext = Depends(require_auth_context),
    db: AsyncSession = Depends(get_chat_session),
) -> AgentStatusResponse:
    """Return session counts and status per agent for the authenticated customer.

    Groups sessions by ``ai_character_name``, returning the total count,
    active task count, and most recent activity timestamp for each agent.
    Sessions without an ``ai_character_name`` are excluded.
    """

    if auth["customer_id"] != customer_id:
        raise HTTPException(status_code=403, detail="Access denied: customer ID mismatch")

    logger.info("Fetching agent status for customer_id=%s", customer_id)

    query = (
        select(
            ChatSession.ai_character_name.label("name"),
            func.count().label("session_count"),
            func.sum(
                case(
                    (ChatSession.task_status.in_(["active", "waiting"]), 1),
                    else_=0,
                )
            ).label("active_task_count"),
            func.max(ChatSession.last_update).label("last_activity"),
        )
        .where(ChatSession.customer_id == customer_id)
        .where(ChatSession.ai_character_name.isnot(None))
        .group_by(ChatSession.ai_character_name)
    )

    result = await db.execute(query)
    rows = result.all()

    agents = [
        AgentStatusItem(
            name=row.name,
            status=compute_agent_status(row.last_activity),
            session_count=row.session_count,
            active_task_count=int(row.active_task_count or 0),
            last_activity=row.last_activity.isoformat() if row.last_activity else None,
        )
        for row in rows
    ]

    logger.info(
        "Agent status retrieved for customer_id=%s agent_count=%s",
        customer_id,
        len(agents),
    )

    return AgentStatusResponse(agents=agents)


__all__ = ["router", "compute_agent_status"]
