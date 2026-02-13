"""Integration tests for chart workflow end-to-end."""

from uuid import uuid4

from features.chat.dependencies import get_chat_history_service
from features.chat.schemas.responses import (
    ChatMessagePayload,
    ChatSessionPayload,
    MessageWritePayload,
    MessageWriteResult,
    SessionDetailResult,
)

class StubChatHistoryService:
    """In-memory chat history service that mimics persistence for tests."""

    def __init__(self):
        self.sessions: dict[str, dict] = {}
        self._message_id = 0

    def _next_message_id(self) -> int:
        self._message_id += 1
        return self._message_id

    async def create_message(self, request):
        session_id = request.session_id or f"session-{uuid4()}"
        user_message_id = self._next_message_id()
        ai_message_id = self._next_message_id()

        user_payload = {
            "message_id": user_message_id,
            "session_id": session_id,
            "customer_id": request.customer_id,
            "sender": request.user_message.sender or "USER",
            "message": request.user_message.message,
            "chart_data": request.user_message.chart_data or None,
        }
        ai_payload = {
            "message_id": ai_message_id,
            "session_id": session_id,
            "customer_id": request.customer_id,
            "sender": request.ai_response.sender or "AI",
            "message": request.ai_response.message,
            "chart_data": request.ai_response.chart_data or None,
        }

        self.sessions[session_id] = {
            "session_id": session_id,
            "customer_id": request.customer_id,
            "session_name": request.session_name or "New chat",
            "messages": [user_payload, ai_payload],
        }

        return MessageWritePayload(
            messages=MessageWriteResult(
                user_message_id=user_message_id,
                ai_message_id=ai_message_id,
                session_id=session_id,
            )
        )

    async def get_session(self, request):
        session_data = self.sessions.get(request.session_id)
        if not session_data:
            raise ValueError("Session not found")

        message_payloads = [
            ChatMessagePayload(**message) for message in session_data["messages"]
        ]
        session_payload = ChatSessionPayload(
            session_id=session_data["session_id"],
            customer_id=session_data["customer_id"],
            session_name=session_data["session_name"],
            messages=message_payloads,
        )
        return SessionDetailResult(session=session_payload)


def test_session_includes_chart_data(chat_test_client, auth_token):
    """Test that session retrieval includes chart_data in messages."""

    stub_service = StubChatHistoryService()
    chat_test_client.app.dependency_overrides[get_chat_history_service] = (
        lambda: stub_service
    )

    chart_payload = {
        "chartId": "chart-test-123",
        "chartType": "pie",
        "title": "Category Breakdown",
        "subtitle": "Agent generated data",
        "data": {
            "labels": ["A", "B", "C"],
            "datasets": [
                {"label": "Share", "data": [45, 30, 25]}
            ],
        },
        "options": {
            "interactive": True,
            "showLegend": True,
            "showGrid": False,
        },
        "dataSource": "llm_generated",
    }

    headers = {"Authorization": f"Bearer {auth_token}"}

    try:
        # 1. Persist a chat session with chart data attached to the AI response.
        create_response = chat_test_client.post(
            "/api/v1/chat/messages",
            headers=headers,
            json={
                "customer_id": 1,
                "session_name": "Chart session",
                "user_message": {
                    "sender": "USER",
                    "message": "Create a pie chart: A (45%), B (30%), C (25%)",
                },
                "ai_response": {
                    "sender": "AI",
                    "message": "Here's your chart!",
                    "chart_data": [chart_payload],
                },
                "include_messages": False,
            },
        )
        create_response.raise_for_status()
        session_id = create_response.json()["data"]["session_id"]

        # 2. Fetch session detail including messages.
        detail_response = chat_test_client.post(
            "/api/v1/chat/sessions/detail",
            headers=headers,
            json={"customer_id": 1, "session_id": session_id, "include_messages": True},
        )
        detail_response.raise_for_status()

        # 3. Verify chart_data in response
        data = detail_response.json()["data"]
        messages = data["messages"]
        ai_message = next(m for m in messages if m["sender"] == "AI")

        assert "chart_data" in ai_message
        assert ai_message["chart_data"] is not None
        assert len(ai_message["chart_data"]) > 0
        first_chart = ai_message["chart_data"][0]
        assert first_chart["chartType"] == "pie"
        assert first_chart["chartId"] == "chart-test-123"
    finally:
        chat_test_client.app.dependency_overrides.pop(
            get_chat_history_service, None
        )
