from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

import pytest

from features.chat.services import group_stream_handler
from features.chat.services.group_router import message_queue


@pytest.mark.asyncio
async def test_handle_group_stream_end_emits_response_and_clears_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    group_id = uuid4()
    request_id = uuid4()

    agent_request = SimpleNamespace(
        group_request_id=request_id,
        agent_name="bugsy",
        proactive_session_id="pa-123",
    )
    group_request = SimpleNamespace(
        id=request_id,
        group_id=group_id,
        group_session_id="group-session-1",
        user_id=1,
        user_message_id=None,
        mode="explicit",
        mentioned_agents=[],
        target_agents=[],
        status="pending",
        next_agent_index=0,
    )
    group = SimpleNamespace(
        id=group_id,
        leader_agent="sherlock",
        context_window_size=6,
        members=[SimpleNamespace(agent_name="bugsy", position=1)],
    )

    repo = SimpleNamespace(
        get_pending_agent_request=AsyncMock(return_value=agent_request),
        get_request_with_agents=AsyncMock(return_value=group_request),
        mark_agent_request_completed=AsyncMock(),
        has_pending_agent_requests=AsyncMock(return_value=False),
        update_request=AsyncMock(),
    )

    service = SimpleNamespace(
        get_group=AsyncMock(return_value=group),
        update_member_response_time=AsyncMock(),
    )

    monkeypatch.setattr(group_stream_handler, "GroupChatRequestRepository", lambda db: repo)
    monkeypatch.setattr(group_stream_handler, "GroupService", lambda db: service)
    push_event = AsyncMock()
    monkeypatch.setattr(group_stream_handler, "push_group_event", push_event)

    db = SimpleNamespace(add=MagicMock(), flush=AsyncMock())

    message_queue.set_pending(group_id, ["bugsy"])

    await group_stream_handler.handle_group_stream_end(
        db=db,
        proactive_session_id="pa-123",
        user_id=1,
        ai_character_name="bugsy",
        content="Hello from Bugsy",
    )

    repo.mark_agent_request_completed.assert_awaited_once()
    assert push_event.await_args.kwargs["event"]["type"] == "agent_response"
    assert message_queue.get_next_agent(group_id) is None
