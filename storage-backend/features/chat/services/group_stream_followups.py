"""Leader/listener and finalization logic for group streams."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from features.chat.group_request_models import GroupChatRequest
from features.chat.repositories.group_request_repository import GroupChatRequestRepository
from features.chat.services.group_router import (
    GroupChatRouter,
    create_listener_system_hint,
    detect_listener_invocation,
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


async def queue_listeners_after_leader(
    *,
    db: AsyncSession,
    group_request: GroupChatRequest,
    group,
    leader_response: str,
    user_id: int,
    repo: GroupChatRequestRepository,
) -> None:
    mentioned_agents = group_request.mentioned_agents or []
    listeners = [m.agent_name for m in group.members if m.agent_name != group.leader_agent]
    invoked = detect_listener_invocation(leader_response, listeners)

    listeners_to_invoke = []
    for agent in mentioned_agents:
        if agent in listeners and agent not in listeners_to_invoke:
            listeners_to_invoke.append(agent)
    for agent in invoked:
        if agent not in listeners_to_invoke:
            listeners_to_invoke.append(agent)

    if not listeners_to_invoke:
        return

    router = GroupChatRouter(db)
    user_message = await get_user_message_text(db, group_request)

    for listener in listeners_to_invoke:
        invoked_by = "user" if listener in mentioned_agents else group.leader_agent
        message_queue.add_pending(group.id, listener)
        await push_group_event(
            user_id=user_id,
            event={
                "type": "agent_typing",
                "group_id": str(group.id),
                "agent_name": listener,
                "role": "listener",
                "invoked_by": invoked_by,
            },
        )

        listener_context = await router.get_context_for_agent(
            group.id,
            listener,
            group_request.group_session_id,
            group.context_window_size,
        )
        if leader_response:
            listener_context.append(
                {
                    "role": "assistant",
                    "agent": group.leader_agent,
                    "content": leader_response,
                    "timestamp": "",
                }
            )

        payload = router.format_context_for_forwarding(
            user_message,
            listener_context,
            group,
            get_member_position(group, listener),
        )
        payload["group_metadata"]["role"] = "listener"
        payload["group_metadata"]["invoked_by"] = invoked_by
        payload["group_metadata"]["system_hint"] = create_listener_system_hint(
            group.leader_agent, is_invoked=True, invoked_by=invoked_by
        )

        result = await route_to_agent(
            agent_name=listener,
            payload=payload,
            session_id=group_request.group_session_id,
            user_id=user_id,
        )

        if result.queued:
            if result.proactive_session_id:
                await repo.create_agent_request(
                    group_request_id=group_request.id,
                    proactive_session_id=result.proactive_session_id,
                    agent_name=listener,
                )
            else:
                logger.error("Queued listener missing proactive session id")
            continue

        if result.response:
            await persist_group_agent_message(
                db=db,
                group_session_id=group_request.group_session_id,
                user_id=user_id,
                agent_name=listener,
                content=result.response,
                chart_data=None,
                ai_reasoning=None,
            )
            await GroupService(db).update_member_response_time(group.id, listener)
            await push_group_event(
                user_id=user_id,
                event={
                    "type": "agent_response",
                    "group_id": str(group.id),
                    "agent_name": listener,
                    "content": result.response,
                    "role": "listener",
                    "invoked_by": invoked_by,
                },
            )
            message_queue.mark_agent_done(group.id, listener)
        else:
            await push_group_event(
                user_id=user_id,
                event={
                    "type": "agent_error",
                    "group_id": str(group.id),
                    "agent_name": listener,
                    "error": "Failed to get response",
                },
            )


async def finalize_group_request_if_done(
    *,
    repo: GroupChatRequestRepository,
    group_request: GroupChatRequest,
    group_id,
) -> None:
    if await repo.has_pending_agent_requests(group_request.id):
        return
    await repo.update_request(group_request, status="completed")
    message_queue.clear(group_id)


__all__ = ["queue_listeners_after_leader", "finalize_group_request_if_done"]
