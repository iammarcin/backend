"""Shared helpers for group stream handling."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.connections import get_proactive_registry
from features.chat.db_models import ChatMessage
from features.chat.group_request_models import GroupChatRequest

async def persist_group_agent_message(
    *,
    db: AsyncSession,
    group_session_id: str,
    user_id: int,
    agent_name: str,
    content: str,
    chart_data: Optional[list[dict]],
    ai_reasoning: Optional[str],
) -> None:
    message = ChatMessage(
        session_id=group_session_id,
        customer_id=user_id,
        sender="AI",
        message=content,
        ai_character_name=agent_name,
        responding_agent=agent_name,
        chart_data=chart_data,
        ai_reasoning=ai_reasoning,
    )
    db.add(message)
    await db.flush()


async def push_group_event(*, user_id: int, event: dict) -> None:
    registry = get_proactive_registry()
    await registry.push_to_user(user_id=user_id, message=event, session_scoped=False)


def sequence_payload(group_request: GroupChatRequest, position: int, total: int) -> dict:
    if group_request.mode != "sequential" or position < 0:
        return {}
    is_last = position == total - 1
    return {"position": position, "is_last": is_last}


def get_member_position(group, agent_name: str) -> int:
    for member in group.members:
        if member.agent_name == agent_name:
            return member.position
    return -1


def get_invoked_by(
    group_request: GroupChatRequest, agent_name: str, leader_agent: str
) -> Optional[str]:
    mentioned_agents = group_request.mentioned_agents or []
    if agent_name in mentioned_agents:
        return "user"
    return leader_agent


async def get_user_message_text(db: AsyncSession, group_request: GroupChatRequest) -> str:
    if group_request.user_message_id:
        return (await load_user_message(db, group_request.user_message_id)) or ""

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == group_request.group_session_id)
        .where(ChatMessage.sender == "User")
        .order_by(ChatMessage.created_at.desc())
        .limit(1)
    )
    message = result.scalar_one_or_none()
    return message.message if message else ""


async def load_user_message(db: AsyncSession, message_id: int) -> Optional[str]:
    result = await db.execute(
        select(ChatMessage).where(ChatMessage.message_id == message_id)
    )
    message = result.scalar_one_or_none()
    return message.message if message else None


__all__ = [
    "persist_group_agent_message",
    "push_group_event",
    "sequence_payload",
    "get_member_position",
    "get_invoked_by",
    "get_user_message_text",
]
