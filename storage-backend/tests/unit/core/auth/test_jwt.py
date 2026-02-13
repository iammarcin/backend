from datetime import timedelta

import pytest
from jose import jwt

from core.auth import AuthenticationError, authenticate_bearer_token, create_auth_token


# Tests for create_auth_token


def test_create_auth_token_basic(auth_token_secret: str) -> None:
    """Test basic token creation."""
    token = create_auth_token(customer_id=123)

    # Verify it's a valid JWT using the test fixture secret
    payload = jwt.decode(token, auth_token_secret, algorithms=["HS256"])

    assert payload["id"] == 123
    assert "exp" in payload


def test_create_auth_token_with_email(auth_token_secret: str) -> None:
    """Test token includes email when provided."""
    token = create_auth_token(customer_id=123, email="test@example.com")

    payload = jwt.decode(token, auth_token_secret, algorithms=["HS256"])

    assert payload["id"] == 123
    assert payload["email"] == "test@example.com"


def test_create_auth_token_custom_expiry(auth_token_secret: str) -> None:
    """Test custom expiry delta."""
    token = create_auth_token(
        customer_id=456,
        expires_delta=timedelta(days=1),
    )

    payload = jwt.decode(token, auth_token_secret, algorithms=["HS256"])
    assert payload["id"] == 456


def test_create_auth_token_can_be_validated() -> None:
    """Test created tokens can be validated by authenticate_bearer_token."""
    token = create_auth_token(customer_id=789, email="user@test.com")

    context = authenticate_bearer_token(authorization=f"Bearer {token}")

    assert context["customer_id"] == 789
    assert context["email"] == "user@test.com"


# Tests for authenticate_bearer_token


def test_authenticate_bearer_token_returns_context(auth_token_factory) -> None:
    token = auth_token_factory(customer_id=42, email="user@example.com")

    context = authenticate_bearer_token(authorization=f"Bearer {token}")

    assert context["customer_id"] == 42
    assert context["email"] == "user@example.com"
    assert context["token"] == token
    assert "payload" in context and context["payload"]["id"] == 42


def test_authenticate_bearer_token_rejects_missing_token() -> None:
    with pytest.raises(AuthenticationError) as exc:
        authenticate_bearer_token()

    assert exc.value.reason == "token_missing"
    assert exc.value.code == 401


def test_authenticate_bearer_token_rejects_expired_token(auth_token_factory) -> None:
    expired_token = auth_token_factory(expires_delta=timedelta(seconds=-1))

    with pytest.raises(AuthenticationError) as exc:
        authenticate_bearer_token(authorization=f"Bearer {expired_token}")

    assert exc.value.reason == "token_expired"


def test_authenticate_bearer_token_rejects_invalid_signature() -> None:
    with pytest.raises(AuthenticationError) as exc:
        authenticate_bearer_token(authorization="Bearer invalid-token")

    assert exc.value.reason == "token_invalid"
