"""Service layer for group chat operations."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable, Iterable, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from features.chat.db_models import ChatGroup, ChatGroupMember
from features.chat.schemas.group_schemas import GroupCreate, GroupUpdate

logger = logging.getLogger(__name__)

MIN_GROUP_MEMBERS = 1
MAX_GROUP_MEMBERS = 20


@dataclass(frozen=True)
class GroupMemberInfo:
    agent_name: str
    position: int


@dataclass(frozen=True)
class GroupMemberUpdatePlan:
    add_agents: list[str]
    remove_agents: list[str]
    remaining_members: list[GroupMemberInfo]
    next_position: int


def _normalize_agent_names(agent_names: Iterable[str], field_name: str) -> list[str]:
    cleaned: list[str] = []
    for agent_name in agent_names:
        if not isinstance(agent_name, str):
            raise ValueError(f"{field_name} must contain strings")
        normalized = agent_name.strip().lower()
        if not normalized:
            raise ValueError(f"{field_name} must not contain empty agent names")
        cleaned.append(normalized)
    if len(set(cleaned)) != len(cleaned):
        raise ValueError(f"{field_name} contains duplicate agent names")
    return cleaned


def _plan_group_member_update(
    *,
    current_members: Iterable[GroupMemberInfo],
    leader_agent: str,
    add_agents: Iterable[str] | None,
    remove_agents: Iterable[str] | None,
    validate_agent: Callable[[str], bool] | None = None,
) -> GroupMemberUpdatePlan:
    normalized_add = _normalize_agent_names(add_agents or [], "add_agents")
    normalized_remove = _normalize_agent_names(remove_agents or [], "remove_agents")

    if set(normalized_add) & set(normalized_remove):
        raise ValueError("Agents cannot be in both add_agents and remove_agents")

    if leader_agent.lower() in normalized_remove:
        raise ValueError("Leader agent cannot be removed")

    current_by_name = {member.agent_name.lower(): member for member in current_members}
    current_names = set(current_by_name.keys())

    normalized_add = [agent for agent in normalized_add if agent not in current_names]
    normalized_remove = [agent for agent in normalized_remove if agent in current_names]

    if validate_agent is not None:
        unknown = [agent for agent in normalized_add if not validate_agent(agent)]
        if unknown:
            raise ValueError(f"Unknown agents: {', '.join(sorted(unknown))}")

    remaining = [
        member for name, member in current_by_name.items() if name not in set(normalized_remove)
    ]

    new_count = len(remaining) + len(normalized_add)
    if new_count < MIN_GROUP_MEMBERS:
        raise ValueError(f"Group must have at least {MIN_GROUP_MEMBERS} member(s)")
    if new_count > MAX_GROUP_MEMBERS:
        raise ValueError(f"Group cannot exceed {MAX_GROUP_MEMBERS} members")

    next_position = max((member.position for member in remaining), default=-1) + 1
    return GroupMemberUpdatePlan(
        add_agents=normalized_add,
        remove_agents=normalized_remove,
        remaining_members=remaining,
        next_position=next_position,
    )


class GroupService:
    """Service for managing group chats."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_group(self, user_id: int, data: GroupCreate) -> ChatGroup:
        """Create a new group chat with specified agents."""
        # Determine leader (first agent, or sherlock if present)
        leader = "sherlock" if "sherlock" in data.agents else data.agents[0]

        group = ChatGroup(
            user_id=user_id,
            name=data.name,
            mode=data.mode.value,
            leader_agent=leader,
            context_window_size=data.context_window_size
        )
        self.db.add(group)
        await self.db.flush()

        # Add members with positions
        for i, agent_name in enumerate(data.agents):
            member = ChatGroupMember(
                group_id=group.id,
                agent_name=agent_name,
                position=i
            )
            self.db.add(member)

        await self.db.commit()
        await self.db.refresh(group)

        # Reload with members
        result = await self.db.execute(
            select(ChatGroup)
            .options(selectinload(ChatGroup.members))
            .where(ChatGroup.id == group.id)
        )
        return result.scalar_one()

    async def get_group(self, group_id: UUID) -> Optional[ChatGroup]:
        """Get a group by ID with its members."""
        result = await self.db.execute(
            select(ChatGroup)
            .options(selectinload(ChatGroup.members))
            .where(ChatGroup.id == group_id)
        )
        return result.scalar_one_or_none()

    async def list_groups(self, user_id: int) -> List[ChatGroup]:
        """List all groups for a user."""
        result = await self.db.execute(
            select(ChatGroup)
            .options(selectinload(ChatGroup.members))
            .where(ChatGroup.user_id == user_id)
            .order_by(ChatGroup.updated_at.desc())
        )
        return list(result.scalars().all())

    async def update_group(self, group_id: UUID, data: GroupUpdate) -> Optional[ChatGroup]:
        """Update group settings (name and context_window_size only)."""
        group = await self.get_group(group_id)
        if not group:
            return None

        if data.name is not None:
            group.name = data.name
        if data.context_window_size is not None:
            group.context_window_size = data.context_window_size

        await self.db.commit()
        await self.db.refresh(group)
        return group

    async def delete_group(self, group_id: UUID) -> bool:
        """Delete a group chat."""
        group = await self.get_group(group_id)
        if not group:
            return False

        await self.db.delete(group)
        await self.db.commit()
        return True

    async def update_member_response_time(self, group_id: UUID, agent_name: str) -> None:
        """Update last_response_at for a member after they respond."""
        result = await self.db.execute(
            select(ChatGroupMember)
            .where(ChatGroupMember.group_id == group_id)
            .where(ChatGroupMember.agent_name == agent_name)
        )
        member = result.scalar_one_or_none()
        if member:
            member.last_response_at = datetime.utcnow()
            await self.db.commit()
            logger.debug(f"Updated response time for {agent_name} in group {group_id}")

    async def update_group_members(
        self,
        group_id: UUID,
        *,
        add_agents: list[str] | None = None,
        remove_agents: list[str] | None = None,
    ) -> Optional[ChatGroup]:
        """Add/remove agents for a group while preserving existing order."""
        group = await self.get_group(group_id)
        if not group:
            return None

        current_members = [
            GroupMemberInfo(agent_name=member.agent_name, position=member.position)
            for member in group.members
        ]

        plan = _plan_group_member_update(
            current_members=current_members,
            leader_agent=group.leader_agent,
            add_agents=add_agents,
            remove_agents=remove_agents,
            validate_agent=None,
        )

        if not plan.add_agents and not plan.remove_agents:
            return group

        members_by_name = {member.agent_name.lower(): member for member in group.members}

        if plan.remove_agents:
            for agent_name in plan.remove_agents:
                member = members_by_name.get(agent_name)
                if member is not None:
                    await self.db.delete(member)

        for offset, agent_name in enumerate(plan.add_agents):
            member = ChatGroupMember(
                group_id=group.id,
                agent_name=agent_name,
                position=plan.next_position + offset,
            )
            self.db.add(member)

        group.updated_at = datetime.now(UTC)
        await self.db.commit()

        result = await self.db.execute(
            select(ChatGroup)
            .options(selectinload(ChatGroup.members))
            .where(ChatGroup.id == group.id)
        )
        return result.scalar_one()
