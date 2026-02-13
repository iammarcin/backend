"""Repository helpers for chat users."""

from __future__ import annotations

import logging

import bcrypt
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import AuthenticationError
from features.chat.db_models import User


logger = logging.getLogger(__name__)


class UserRepository:
    """Lookup and authentication helpers for :class:`User` rows."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_user(self, *, customer_id: int, email: str) -> User | None:
        query = select(User).where(
            User.customer_id == customer_id,
            User.email == email,
        )
        result = await self._session.execute(query)
        return result.scalars().first()

    async def verify_credentials(
        self,
        *,
        customer_id: int,
        username: str,
        password: str,
    ) -> User:
        """Return the user when credentials are valid; raise otherwise."""

        logger.info(
            "Authenticating chat user for username=%s",
            username,
        )
        query = select(User).where(
            or_(User.email == username, User.username == username),
        )
        result = await self._session.execute(query)
        user = result.scalars().first()
        if user is None:
            logger.warning(
                "Chat authentication failed: user not found (customer_id=%s username=%s)",
                customer_id,
                username,
            )
            raise AuthenticationError("Invalid username or password")

        password_hash = user.password
        if not password_hash:
            logger.error(
                "Chat authentication failed: missing password hash (customer_id=%s username=%s)",
                customer_id,
                username,
            )
            raise AuthenticationError("Invalid username or password")

        try:
            password_valid = bcrypt.checkpw(
                password.encode("utf-8"), password_hash.encode("utf-8")
            )
        except (TypeError, ValueError) as exc:
            logger.exception(
                "Chat authentication failed: password hash verification error for customer_id=%s username=%s",
                customer_id,
                username,
            )
            raise AuthenticationError("Invalid username or password") from exc

        if not password_valid:
            logger.warning(
                "Chat authentication failed: invalid credentials (customer_id=%s username=%s)",
                customer_id,
                username,
            )
            raise AuthenticationError("Invalid username or password")

        logger.info(
            "Chat authentication succeeded for customer_id=%s username=%s",
            customer_id,
            username,
        )
        return user


__all__ = ["UserRepository"]

