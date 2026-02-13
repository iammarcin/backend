from collections.abc import AsyncIterator, Iterator
from datetime import datetime
from types import SimpleNamespace
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from core.exceptions import AuthenticationError, DatabaseError, ValidationError
from features.db.ufc.dependencies import get_ufc_service, get_ufc_session
from features.db.ufc.schemas import (
    AuthLoginRequest,
    AuthResult,
    RegistrationResult,
    UserExistsResult,
    UserProfile,
)
from main import app


@pytest.fixture(autouse=True)
def reset_dependency_overrides() -> Iterator[None]:
    try:
        yield
    finally:
        app.dependency_overrides.clear()


async def _fake_session_dependency() -> AsyncIterator[SimpleNamespace]:
    yield SimpleNamespace()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_login_returns_profile_envelope() -> None:
    profile = UserProfile(
        id=5,
        accountName="Tester",
        email="tester@example.com",
        lang="en",
        totalGenerations=1,
        photo="avatar.png",
        createdAt=datetime(2024, 1, 1, 12, 0, 0),
    )
    auth_result = AuthResult(
        status="authenticated",
        message="User authenticated",
        token="token-xyz",
        user=profile,
    )

    class StubService:
        async def authenticate_user(self, session: Any, payload: AuthLoginRequest) -> AuthResult:
            self.payload = payload
            return auth_result

    service = StubService()
    app.dependency_overrides[get_ufc_service] = lambda: service
    app.dependency_overrides[get_ufc_session] = _fake_session_dependency

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/ufc/auth/login",
            json={"email": "tester@example.com", "password": "password123"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["user"]["accountName"] == "Tester"
    assert payload["meta"]["tokenProvided"] is True
    assert isinstance(service.payload, AuthLoginRequest)


@pytest.mark.anyio
async def test_login_invalid_credentials_returns_401() -> None:
    class StubService:
        async def authenticate_user(self, session: Any, payload: AuthLoginRequest) -> AuthResult:
            raise AuthenticationError("Invalid email or password")

    app.dependency_overrides[get_ufc_service] = lambda: StubService()
    app.dependency_overrides[get_ufc_session] = _fake_session_dependency

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/ufc/auth/login",
            json={"email": "tester@example.com", "password": "wrongpass"},
        )

    assert response.status_code == 401
    payload = response.json()
    assert payload["code"] == 401
    assert payload["success"] is False


@pytest.mark.anyio
async def test_register_duplicate_returns_409() -> None:
    class StubService:
        async def register_user(self, session: Any, payload: Any) -> RegistrationResult:
            raise DatabaseError("User already exists", operation="register_user_duplicate")

    app.dependency_overrides[get_ufc_service] = lambda: StubService()
    app.dependency_overrides[get_ufc_session] = _fake_session_dependency

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/ufc/auth/register",
            json={"accountName": "Test", "email": "test@example.com", "password": "password123"},
        )

    assert response.status_code == 409
    payload = response.json()
    assert payload["code"] == 409
    assert payload["success"] is False


@pytest.mark.anyio
async def test_user_exists_endpoint_returns_boolean() -> None:
    result = UserExistsResult(email="exists@example.com", exists=False, message="User not found")

    class StubService:
        async def user_exists(self, session: Any, email: str) -> UserExistsResult:
            return result

    app.dependency_overrides[get_ufc_service] = lambda: StubService()
    app.dependency_overrides[get_ufc_session] = _fake_session_dependency

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/ufc/users/exists@example.com/exists")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["exists"] is False
    assert payload["data"]["email"] == "exists@example.com"


@pytest.mark.anyio
async def test_get_user_profile_not_found_returns_404() -> None:
    class StubService:
        async def get_user_profile(self, session: Any, email: str) -> UserProfile:
            raise ValidationError("User not found", field="email")

    app.dependency_overrides[get_ufc_service] = lambda: StubService()
    app.dependency_overrides[get_ufc_session] = _fake_session_dependency

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/ufc/users/missing@example.com")

    assert response.status_code == 404
    payload = response.json()
    assert payload["code"] == 404
    assert payload["success"] is False
