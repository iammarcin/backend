"""Regression tests verifying chat history endpoints emit modern API envelopes."""

from __future__ import annotations

from typing import Iterator

import pytest
from httpx import ASGITransport, AsyncClient

from features.chat.dependencies import get_chat_history_service
from features.chat.schemas.responses import (
    AuthResult,
    ChatMessagePayload,
    ChatSessionPayload,
    FavoritesResult,
    FileQueryResult,
    MessageUpdateResult,
    MessageWritePayload,
    MessageWriteResult,
    MessagesRemovedResult,
    PromptListResult,
    PromptRecord,
    SessionDetailResult,
    SessionListResult,
)
from main import app


@pytest.fixture(autouse=True)
def reset_overrides() -> Iterator[None]:
    try:
        yield
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def _request(
    method: str,
    path: str,
    *,
    json: dict | None = None,
    params: dict | None = None,
    auth_token: str | None = None,
):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        if auth_token:
            client.headers.update({"Authorization": f"Bearer {auth_token}"})
        request_kwargs: dict[str, object] = {}
        if params is not None:
            request_kwargs["params"] = params
        if json is not None:
            request_kwargs["json"] = json
        response = await client.request(method.upper(), path, **request_kwargs)
    return response


@pytest.mark.anyio
async def test_create_message_response_is_flattened(auth_token: str) -> None:
    class StubService:
        async def create_message(self, request):
            return MessageWritePayload(
                messages=MessageWriteResult(
                    user_message_id=11,
                    ai_message_id=12,
                    session_id="sess-create",
                ),
                session=None,
            )

    app.dependency_overrides[get_chat_history_service] = lambda: StubService()

    response = await _request(
        "post",
        "/api/v1/chat/messages",
        json={"customer_id": 1, "user_message": {"message": "hi"}},
        auth_token=auth_token,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["user_message_id"] == 11
    assert "messages" not in payload["data"]


@pytest.mark.anyio
async def test_update_message_response_preserves_aliases(auth_token: str) -> None:
    class StubService:
        async def update_message(self, request):
            return MessageUpdateResult(message_id=88)

    app.dependency_overrides[get_chat_history_service] = lambda: StubService()

    response = await _request(
        "put",
        "/api/v1/chat/messages",
        json={"customer_id": 1, "message_id": 88, "patch": {"message": "updated"}},
        auth_token=auth_token,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["message_id"] == 88


@pytest.mark.anyio
async def test_list_sessions_response_uses_aliases(auth_token: str) -> None:
    class StubService:
        async def list_sessions(self, request):
            return SessionListResult(
                sessions=[
                    ChatSessionPayload(
                        session_id="s-1",
                        customer_id=1,
                        session_name="One",
                    )
                ],
                count=1,
            )

    app.dependency_overrides[get_chat_history_service] = lambda: StubService()

    response = await _request(
        "post",
        "/api/v1/chat/sessions/list",
        json={"customer_id": 1},
        auth_token=auth_token,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["sessions"][0]["session_id"] == "s-1"
    assert payload["data"]["count"] == 1


@pytest.mark.anyio
async def test_session_detail_response_returns_session_payload(auth_token: str) -> None:
    class StubService:
        async def get_session(self, request):
            return SessionDetailResult(
                session=ChatSessionPayload(
                    session_id="s-2",
                    customer_id=1,
                    session_name="Detail",
                )
            )

    app.dependency_overrides[get_chat_history_service] = lambda: StubService()

    response = await _request(
        "post",
        "/api/v1/chat/sessions/detail",
        json={"customer_id": 1, "session_id": "s-2"},
        auth_token=auth_token,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["session_id"] == "s-2"
    assert payload["data"]["session_name"] == "Detail"


@pytest.mark.anyio
async def test_favorites_response_handles_missing_session(auth_token: str) -> None:
    class StubService:
        async def get_favorites(self, request):
            return FavoritesResult(session=None)

    app.dependency_overrides[get_chat_history_service] = lambda: StubService()

    response = await _request(
        "get",
        "/api/v1/chat/maintenance/favorites",
        params={"customer_id": 1},
        auth_token=auth_token,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"] == {}


@pytest.mark.anyio
async def test_query_files_response_uses_aliases(auth_token: str) -> None:
    class StubService:
        async def query_files(self, request):
            return FileQueryResult(
                messages=[
                    ChatMessagePayload(
                        message_id=5,
                        session_id="sess",
                        customer_id=1,
                        sender="AI",
                    )
                ]
            )

    app.dependency_overrides[get_chat_history_service] = lambda: StubService()

    response = await _request(
        "post",
        "/api/v1/chat/maintenance/files",
        json={"customer_id": 1},
        auth_token=auth_token,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["messages"][0]["message_id"] == 5


@pytest.mark.anyio
async def test_prompt_list_response_uses_aliases(auth_token: str) -> None:
    class StubService:
        async def list_prompts(self, request):
            return PromptListResult(
                prompts=[
                    PromptRecord(
                        prompt_id=3,
                        customer_id=1,
                        title="Hello",
                        prompt="Hi",
                    )
                ]
            )

    app.dependency_overrides[get_chat_history_service] = lambda: StubService()

    response = await _request(
        "get",
        "/api/v1/chat/prompts",
        params={"customer_id": 1},
        auth_token=auth_token,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["prompts"][0]["prompt_id"] == 3


@pytest.mark.anyio
async def test_auth_login_response_uses_aliases(auth_token: str) -> None:
    class StubService:
        async def auth_login(self, request):  # pragma: no cover - attribute name shim
            raise RuntimeError("Should not be called")

        async def authenticate(self, request):
            return AuthResult(customer_id=7, username="user", token="stub-token")

    app.dependency_overrides[get_chat_history_service] = lambda: StubService()

    response = await _request(
        "post",
        "/api/v1/chat/auth/login",
        json={"customer_id": 7, "username": "user", "password": "secret"},
        auth_token=auth_token,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["customer_id"] == 7
    assert payload["data"]["username"] == "user"


@pytest.mark.anyio
async def test_remove_messages_response_excludes_nones(auth_token: str) -> None:
    class StubService:
        async def remove_messages(self, request):
            return MessagesRemovedResult(removed_count=2, message_ids=[1, 2], session_id="sess")

    app.dependency_overrides[get_chat_history_service] = lambda: StubService()

    response = await _request(
        "delete",
        "/api/v1/chat/messages",
        json={"customer_id": 1, "session_id": "sess", "message_ids": [1, 2]},
        auth_token=auth_token,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["removed_count"] == 2
    assert payload["data"]["session_id"] == "sess"
