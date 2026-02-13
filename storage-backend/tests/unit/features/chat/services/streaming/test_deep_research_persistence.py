from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest

from features.chat.services.streaming.deep_research_persistence import (
    ensure_session_exists,
    save_deep_research_to_db,
)


class _StubSession:
    def __init__(self) -> None:
        self.messages: List[Dict[str, Any]] = []
        self.metadata_updates: List[Dict[str, Any]] = []
        self.session: Optional[SimpleNamespace] = None
        self.notification_tags: List[str] = []


class _StubMessageRepository:
    def __init__(self, session: _StubSession) -> None:
        self._session = session

    async def insert_message(
        self,
        *,
        session_id: str,
        customer_id: int,
        payload: Dict[str, Any],
        is_ai_message: bool,
        claude_code_data: Dict[str, Any] | None = None,
        use_date_override: bool = False,
    ) -> SimpleNamespace:
        message_id = len(self._session.messages) + 1
        entry = {
            "session_id": session_id,
            "customer_id": customer_id,
            "payload": payload,
            "is_ai": is_ai_message,
            "claude_code_data": claude_code_data,
            "use_date_override": use_date_override,
        }
        self._session.messages.append(entry)
        return SimpleNamespace(message_id=message_id, customer_id=customer_id)

    async def update_message_metadata(
        self,
        *,
        message_id: int,
        customer_id: int,
        metadata_updates: Dict[str, Any],
    ) -> SimpleNamespace:
        self._session.metadata_updates.append(
            {
                "message_id": message_id,
                "customer_id": customer_id,
                "metadata_updates": metadata_updates,
            }
        )
        return SimpleNamespace(message_id=message_id, customer_id=customer_id)


class _StubSessionRepository:
    def __init__(self, session: _StubSession) -> None:
        self._session = session

    async def get_by_id(
        self,
        session_id: str,
        *,
        customer_id: int,
        include_messages: bool = False,
    ) -> Optional[SimpleNamespace]:
        if self._session.session and self._session.session.session_id == session_id:
            return self._session.session
        return None

    async def create_session(
        self,
        *,
        customer_id: int,
        session_name: str,
        ai_character_name: str,
        tags: List[str],
    ) -> SimpleNamespace:
        self._session.session = SimpleNamespace(
            session_id="generated-session",
            customer_id=customer_id,
            session_name=session_name,
            ai_character_name=ai_character_name,
            tags=tags,
        )
        return self._session.session

    async def add_notification_tag(self, *, session_id: str, customer_id: int) -> None:
        self._session.notification_tags.append(session_id)


@pytest.mark.asyncio
async def test_save_deep_research_to_db_persists_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = _StubSession()

    monkeypatch.setattr(
        "features.chat.services.streaming.deep_research_artifacts.ChatMessageRepository",
        _StubMessageRepository,
    )
    monkeypatch.setattr(
        "features.chat.services.streaming.deep_research_artifacts.ChatSessionRepository",
        _StubSessionRepository,
    )

    message_ids = await save_deep_research_to_db(
        session_id="session-1",
        customer_id=42,
        optimized_prompt="Today is 2025-01-01\nDeep research",
        research_response="Research output",
        citations=[{"title": "Source", "url": "https://example.com"}],
        ai_character_name="assistant",
        primary_model_name="gpt-4o",
        db_session=stub,
    )

    assert message_ids == {"user_message_id": 1, "ai_message_id": 2}
    assert len(stub.messages) == 2
    assert stub.messages[0]["is_ai"] is False
    assert stub.messages[1]["is_ai"] is True
    assert stub.notification_tags == ["session-1"]
    assert stub.metadata_updates[0]["metadata_updates"]["claude_code_data"][
        "citations_count"
    ] == 1


@pytest.mark.asyncio
async def test_ensure_session_exists_creates_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = _StubSession()
    monkeypatch.setattr(
        "features.chat.services.streaming.deep_research_sessions.ChatSessionRepository",
        _StubSessionRepository,
    )

    session_id = await ensure_session_exists(
        session_id=None,
        customer_id=99,
        session_name="Deep Research Session",
        ai_character_name="assistant",
        db_session=stub,
    )

    assert session_id == "generated-session"
    assert stub.session is not None
    assert "notification" in stub.session.tags

    reused = await ensure_session_exists(
        session_id="generated-session",
        customer_id=99,
        session_name="unused",
        ai_character_name="assistant",
        db_session=stub,
    )
    assert reused == "generated-session"
