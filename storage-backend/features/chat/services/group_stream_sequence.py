"""Sequential mode continuation for group streams."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from features.chat.group_request_models import GroupChatRequest
from features.chat.repositories.group_request_repository import GroupChatRequestRepository
from features.chat.services.group_router import (
    GroupChatRouter,
    create_sequential_system_hint,
    message_queue,
)
from features.chat.services.group_service import GroupService
from features.chat.utils.agent_router import route_to_agent
from features.chat.services.group_stream_utils import (
    get_member_position,
    get_user_message_text,
    persist_group_agent_message,
    push_group_event,
)

logger = logging.getLogger(__name__)


async def continue_sequential_flow(
    *,
    db: AsyncSession,
    group_request: GroupChatRequest,
    group,
    user_id: int,
    repo: GroupChatRequestRepository,
) -> None:
    target_agents = list(group_request.target_agents or [])
    next_index = group_request.next_agent_index

    router = GroupChatRouter(db)
    user_message = await get_user_message_text(db, group_request)

    while next_index < len(target_agents):
        agent_name = target_agents[next_index]
        await push_group_event(
            user_id=user_id,
            event={
                "type": "agent_typing",
                "group_id": str(group.id),
                "agent_name": agent_name,
                "position": next_index,
                "total": len(target_agents),
            },
        )

        context = await router.get_context_for_agent(
            group.id,
            agent_name,
            group_request.group_session_id,
            group.context_window_size,
        )
        payload = router.format_context_for_forwarding(
            user_message,
            context,
            group,
            get_member_position(group, agent_name),
        )
        payload["group_metadata"]["previous_responses_this_round"] = next_index
        previous_agents = target_agents[:next_index]
        payload["group_metadata"]["sequential_hint"] = create_sequential_system_hint(
            next_index, len(target_agents), previous_agents
        )

        result = await route_to_agent(
            agent_name=agent_name,
            payload=payload,
            session_id=group_request.group_session_id,
            user_id=user_id,
        )

        if result.queued:
            if result.proactive_session_id:
                await repo.create_agent_request(
                    group_request_id=group_request.id,
                    proactive_session_id=result.proactive_session_id,
                    agent_name=agent_name,
                )
                next_index += 1
                await repo.update_request(group_request, next_agent_index=next_index)
            else:
                logger.error("Queued sequential agent missing proactive session id")
            return

        if result.response:
            await persist_group_agent_message(
                db=db,
                group_session_id=group_request.group_session_id,
                user_id=user_id,
                agent_name=agent_name,
                content=result.response,
                chart_data=None,
                ai_reasoning=None,
            )
            await GroupService(db).update_member_response_time(group.id, agent_name)
            await push_group_event(
                user_id=user_id,
                event={
                    "type": "agent_response",
                    "group_id": str(group.id),
                    "agent_name": agent_name,
                    "content": result.response,
                    "position": next_index,
                    "is_last": next_index == len(target_agents) - 1,
                },
            )
            message_queue.mark_agent_done(group.id, agent_name)
        else:
            await push_group_event(
                user_id=user_id,
                event={
                    "type": "agent_error",
                    "group_id": str(group.id),
                    "agent_name": agent_name,
                    "error": "Failed to get response",
                },
            )

        next_index += 1
        await repo.update_request(group_request, next_agent_index=next_index)

    await push_group_event(
        user_id=user_id,
        event={
            "type": "sequence_complete",
            "group_id": str(group.id),
            "agents_responded": len(target_agents),
        },
    )
    message_queue.clear(group.id)
    await repo.update_request(group_request, status="completed")


__all__ = ["continue_sequential_flow"]
