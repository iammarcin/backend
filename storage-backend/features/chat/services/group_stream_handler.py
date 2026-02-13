"""Handle Claude SDK stream completion for group chat correlation."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from features.chat.repositories.group_request_repository import GroupChatRequestRepository
from features.chat.services.group_router import message_queue
from features.chat.services.group_service import GroupService
from features.chat.services.group_stream_sequence import continue_sequential_flow
from features.chat.services.group_stream_followups import (
    finalize_group_request_if_done,
    queue_listeners_after_leader,
)
from features.chat.services.group_stream_utils import (
    get_invoked_by,
    get_member_position,
    persist_group_agent_message,
    push_group_event,
    sequence_payload,
)

async def handle_group_stream_end(
    *,
    db: AsyncSession,
    proactive_session_id: str,
    user_id: int,
    ai_character_name: str,
    content: Optional[str],
    chart_data: Optional[list[dict]] = None,
    ai_reasoning: Optional[str] = None,
) -> None:
    """Persist group response and continue any pending group workflow."""
    if not proactive_session_id:
        return

    repo = GroupChatRequestRepository(db)
    agent_request = await repo.get_pending_agent_request(proactive_session_id)
    if not agent_request:
        return

    group_request = await repo.get_request_with_agents(agent_request.group_request_id)
    if not group_request or group_request.status != "pending":
        return

    group_id = group_request.group_id
    group_session_id = group_request.group_session_id

    service = GroupService(db)
    group = await service.get_group(group_id)
    if not group:
        return

    member_position = get_member_position(group, agent_request.agent_name)
    total_members = len(group.members)

    await repo.mark_agent_request_completed(agent_request)

    if content:
        await persist_group_agent_message(
            db=db,
            group_session_id=group_session_id,
            user_id=user_id,
            agent_name=agent_request.agent_name,
            content=content,
            chart_data=chart_data,
            ai_reasoning=ai_reasoning,
        )
        await service.update_member_response_time(group_id, agent_request.agent_name)

        event = {
            "type": "agent_response",
            "group_id": str(group_id),
            "agent_name": agent_request.agent_name,
            "content": content,
            **sequence_payload(group_request, member_position, total_members),
        }
        if group_request.mode == "leader_listeners":
            if agent_request.agent_name == group.leader_agent:
                event["role"] = "leader"
            else:
                event["role"] = "listener"
                invoked_by = get_invoked_by(group_request, agent_request.agent_name, group.leader_agent)
                if invoked_by:
                    event["invoked_by"] = invoked_by
        await push_group_event(user_id=user_id, event=event)

    message_queue.mark_agent_done(group_id, agent_request.agent_name)

    if group_request.mode == "sequential":
        await continue_sequential_flow(
            db=db,
            group_request=group_request,
            group=group,
            user_id=user_id,
            repo=repo,
        )
        return

    if group_request.mode == "leader_listeners":
        if agent_request.agent_name == group.leader_agent:
            await queue_listeners_after_leader(
                db=db,
                group_request=group_request,
                group=group,
                leader_response=content or "",
                user_id=user_id,
                repo=repo,
            )
        await finalize_group_request_if_done(
            repo=repo,
            group_request=group_request,
            group_id=group_id,
        )
        return

    await finalize_group_request_if_done(
        repo=repo,
        group_request=group_request,
        group_id=group_id,
    )


__all__ = ["handle_group_stream_end"]
