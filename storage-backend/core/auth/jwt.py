"""Centralised JWT authentication helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Annotated, Any, Dict, TypedDict

from fastapi import Header, Query
from jose import ExpiredSignatureError, JWTError, jwt
from starlette import status

from core.utils.env import get_env


class AuthContext(TypedDict, total=False):
    """Context extracted from a validated authentication token."""

    customer_id: int
    email: str | None
    token: str
    payload: Dict[str, Any]


@dataclass(slots=True)
class AuthenticationError(Exception):
    """Raised when authentication fails for HTTP or WebSocket requests."""

    message: str
    reason: str
    code: int = status.HTTP_401_UNAUTHORIZED

    def __str__(self) -> str:  # pragma: no cover - dataclass repr fallback
        return self.message


@lru_cache(maxsize=1)
def _get_secret() -> str:
    secret = get_env("MY_AUTH_TOKEN", required=True)
    if not secret:
        raise AuthenticationError("Authentication secret is not configured", reason="configuration")
    return secret


def create_auth_token(
    customer_id: int,
    email: str | None = None,
    expires_delta: timedelta = timedelta(days=90),
) -> str:
    """Create a JWT token for the given customer.

    Args:
        customer_id: The customer's ID (stored as 'id' in payload)
        email: Optional email to include in token
        expires_delta: Token validity period (default 90 days)

    Returns:
        Encoded JWT token string
    """
    secret = _get_secret()
    expire = datetime.now(timezone.utc) + expires_delta
    payload: Dict[str, Any] = {
        "id": customer_id,
        "email": email,
        "exp": expire,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None

    parts = authorization.strip().split()
    if not parts:
        return None

    if parts[0].lower() == "bearer":
        return parts[1] if len(parts) > 1 else None

    if len(parts) == 1:
        return parts[0]

    return parts[-1]


def authenticate_bearer_token(
    *,
    authorization: str | None = None,
    query_token: str | None = None,
) -> AuthContext:
    """Validate a bearer token sourced from headers or query parameters."""

    token = _extract_bearer_token(authorization)
    if not token and query_token:
        token = query_token.strip() or None

    if not token:
        raise AuthenticationError("Missing authentication token", reason="token_missing")

    secret = _get_secret()

    try:
        payload: Dict[str, Any] = jwt.decode(token, secret, algorithms=["HS256"])
    except ExpiredSignatureError as exc:
        raise AuthenticationError("Authentication token has expired", reason="token_expired") from exc
    except JWTError as exc:
        raise AuthenticationError("Invalid authentication token", reason="token_invalid") from exc

    user_id = payload.get("id")
    if user_id is None:
        raise AuthenticationError("Authentication token missing user id", reason="token_invalid")

    try:
        customer_id = int(user_id)
    except (TypeError, ValueError) as exc:
        raise AuthenticationError("Invalid customer identifier in token", reason="token_invalid") from exc

    context: AuthContext = {
        "customer_id": customer_id,
        "email": payload.get("email"),
        "token": token,
        "payload": payload,
    }
    return context


def require_auth_context(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    token: Annotated[str | None, Query(alias="token")] = None,
) -> AuthContext:
    """FastAPI dependency returning the authentication context."""

    return authenticate_bearer_token(authorization=authorization, query_token=token)


__all__ = [
    "AuthContext",
    "AuthenticationError",
    "authenticate_bearer_token",
    "create_auth_token",
    "require_auth_context",
]
