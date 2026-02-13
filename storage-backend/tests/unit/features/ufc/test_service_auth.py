import pytest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from core.exceptions import AuthenticationError, ValidationError
from features.db.ufc.schemas.requests import AuthLoginRequest, AuthRegistrationRequest
from features.db.ufc.service import UfcService


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_authenticate_user_returns_profile_and_token() -> None:
    auth_repo = AsyncMock()
    user = SimpleNamespace(
        id=7,
        account_name="Tester",
        email="tester@example.com",
        lang="en",
        total_generations=3,
        photo="avatar.png",
        created_at=datetime(2024, 1, 1, 12, 0, 0),
    )
    auth_repo.authenticate_user.return_value = user

    service = UfcService(auth_repo=auth_repo, token_provider=lambda: "token-123")
    session = SimpleNamespace()
    payload = AuthLoginRequest(email="Tester@example.com", password="password123")

    result = await service.authenticate_user(session, payload)

    auth_repo.authenticate_user.assert_awaited_once()
    assert auth_repo.authenticate_user.await_args.kwargs["email"] == "tester@example.com"
    assert result.status == "authenticated"
    assert result.user.accountName == "Tester"
    assert result.token == "token-123"


@pytest.mark.anyio
async def test_authenticate_user_invalid_credentials() -> None:
    auth_repo = AsyncMock()
    auth_repo.authenticate_user.return_value = None
    service = UfcService(auth_repo=auth_repo)
    session = SimpleNamespace()
    payload = AuthLoginRequest(email="user@example.com", password="password123")

    with pytest.raises(AuthenticationError):
        await service.authenticate_user(session, payload)


@pytest.mark.anyio
async def test_register_user_returns_registration_result() -> None:
    auth_repo = AsyncMock()
    user = SimpleNamespace(
        id=8,
        account_name="New User",
        email="new@example.com",
        lang="en",
        total_generations=0,
        photo="default_photo.png",
        created_at=datetime.now(UTC),
    )
    auth_repo.register_user.return_value = user

    service = UfcService(auth_repo=auth_repo, min_password_length=6)
    session = SimpleNamespace()
    payload = AuthRegistrationRequest(
        accountName="New User",
        email="New@example.com",
        password="secret!!",
    )

    result = await service.register_user(session, payload)

    auth_repo.register_user.assert_awaited_once()
    assert auth_repo.register_user.await_args.kwargs["email"] == "new@example.com"
    assert result.status == "registered"
    assert result.user_id == 8
    assert result.accountName == "New User"


@pytest.mark.anyio
async def test_register_user_enforces_password_length() -> None:
    service = UfcService(min_password_length=12)
    session = SimpleNamespace()
    payload = AuthRegistrationRequest(
        accountName="Short Password",
        email="short@example.com",
        password="shortpass",
    )

    with pytest.raises(ValidationError):
        await service.register_user(session, payload)


@pytest.mark.anyio
async def test_user_exists_trims_and_lowercases_email() -> None:
    auth_repo = AsyncMock()
    auth_repo.user_exists.return_value = True
    service = UfcService(auth_repo=auth_repo)
    session = SimpleNamespace()

    result = await service.user_exists(session, "  USER@Example.com  ")

    auth_repo.user_exists.assert_awaited_once()
    assert auth_repo.user_exists.await_args.kwargs["email"] == "user@example.com"
    assert result.exists is True
    assert result.email == "user@example.com"


@pytest.mark.anyio
async def test_get_user_profile_raises_when_missing() -> None:
    auth_repo = AsyncMock()
    auth_repo.get_user_profile.return_value = None
    service = UfcService(auth_repo=auth_repo)
    session = SimpleNamespace()

    with pytest.raises(ValidationError) as exc_info:
        await service.get_user_profile(session, "missing@example.com")

    assert exc_info.value.field == "email"
