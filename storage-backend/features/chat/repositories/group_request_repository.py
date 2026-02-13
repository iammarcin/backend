"""Repositories for group chat request correlation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from features.chat.group_request_models import GroupChatAgentRequest, GroupChatRequest


class GroupChatRequestRepository:
    """DB access for group chat request correlation records."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_request(
        self,
        *,
        group_id: UUID,
        group_session_id: str,
        user_id: int,
        user_message_id: Optional[int],
        mode: str,
        target_agents: Optional[List[str]] = None,
        mentioned_agents: Optional[List[str]] = None,
    ) -> GroupChatRequest:
        request = GroupChatRequest(
            group_id=group_id,
            group_session_id=group_session_id,
            user_id=user_id,
            user_message_id=user_message_id,
            mode=mode,
            target_agents=target_agents or [],
            mentioned_agents=mentioned_agents or [],
            next_agent_index=0,
            status="pending",
        )
        self.db.add(request)
        await self.db.flush()
        return request

    async def create_agent_request(
        self,
        *,
        group_request_id: UUID,
        proactive_session_id: str,
        agent_name: str,
    ) -> GroupChatAgentRequest:
        agent_request = GroupChatAgentRequest(
            group_request_id=group_request_id,
            proactive_session_id=proactive_session_id,
            agent_name=agent_name,
            status="pending",
        )
        self.db.add(agent_request)
        await self.db.flush()
        return agent_request

    async def get_request_with_agents(self, request_id: UUID) -> Optional[GroupChatRequest]:
        result = await self.db.execute(
            select(GroupChatRequest)
            .options(selectinload(GroupChatRequest.agent_requests))
            .where(GroupChatRequest.id == request_id)
        )
        return result.scalar_one_or_none()

    async def get_pending_agent_request(
        self, proactive_session_id: str
    ) -> Optional[GroupChatAgentRequest]:
        result = await self.db.execute(
            select(GroupChatAgentRequest)
            .where(GroupChatAgentRequest.proactive_session_id == proactive_session_id)
            .where(GroupChatAgentRequest.status == "pending")
            .order_by(GroupChatAgentRequest.created_at.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def mark_agent_request_completed(
        self,
        agent_request: GroupChatAgentRequest,
        status: str = "completed",
    ) -> None:
        agent_request.status = status
        agent_request.completed_at = datetime.now(UTC)
        await self.db.flush()

    async def update_request(
        self,
        request: GroupChatRequest,
        *,
        next_agent_index: Optional[int] = None,
        status: Optional[str] = None,
        target_agents: Optional[List[str]] = None,
        mentioned_agents: Optional[List[str]] = None,
    ) -> None:
        if next_agent_index is not None:
            request.next_agent_index = next_agent_index
        if status is not None:
            request.status = status
        if target_agents is not None:
            request.target_agents = target_agents
        if mentioned_agents is not None:
            request.mentioned_agents = mentioned_agents
        await self.db.flush()

    async def get_latest_agent_session(
        self, group_id: UUID, agent_name: str
    ) -> Optional[str]:
        """Get most recent proactive session ID for an agent in a group.

        Used to reuse Claude SDK sessions across rounds so agents keep
        conversation history instead of starting fresh each time.
        """
        result = await self.db.execute(
            select(GroupChatAgentRequest.proactive_session_id)
            .join(GroupChatRequest, GroupChatAgentRequest.group_request_id == GroupChatRequest.id)
            .where(GroupChatRequest.group_id == group_id)
            .where(GroupChatAgentRequest.agent_name == agent_name)
            .order_by(GroupChatAgentRequest.created_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return row

    async def has_pending_agent_requests(self, request_id: UUID) -> bool:
        result = await self.db.execute(
            select(GroupChatAgentRequest)
            .where(GroupChatAgentRequest.group_request_id == request_id)
            .where(GroupChatAgentRequest.status == "pending")
            .limit(1)
        )
        return result.scalar_one_or_none() is not None


__all__ = ["GroupChatRequestRepository"]
