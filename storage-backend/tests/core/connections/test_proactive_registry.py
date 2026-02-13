import pytest

from core.connections.proactive_registry import ProactiveConnectionRegistry


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent = []

    async def send_json(self, message):
        self.sent.append(message)


@pytest.mark.asyncio
async def test_push_to_user_filters_by_session_id():
    registry = ProactiveConnectionRegistry()
    ws_a = FakeWebSocket()
    ws_b = FakeWebSocket()

    await registry.register(user_id=1, session_id="session-a", websocket=ws_a)
    await registry.register(user_id=1, session_id="session-b", websocket=ws_b)

    pushed = await registry.push_to_user(
        user_id=1,
        message={"type": "notification", "data": {"session_id": "session-a"}},
    )

    assert pushed is True
    assert len(ws_a.sent) == 1
    assert len(ws_b.sent) == 0


@pytest.mark.asyncio
async def test_push_to_user_broadcasts_without_session_id():
    registry = ProactiveConnectionRegistry()
    ws_a = FakeWebSocket()
    ws_b = FakeWebSocket()

    await registry.register(user_id=1, session_id="session-a", websocket=ws_a)
    await registry.register(user_id=1, session_id="session-b", websocket=ws_b)

    pushed = await registry.push_to_user(
        user_id=1,
        message={"type": "ping"},
    )

    assert pushed is True
    assert len(ws_a.sent) == 1
    assert len(ws_b.sent) == 1
