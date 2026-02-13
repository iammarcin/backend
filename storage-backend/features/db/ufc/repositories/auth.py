"""Authentication repository for UFC user accounts."""

from __future__ import annotations

import logging
from typing import Optional

import bcrypt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import DatabaseError

from ..db_models import Person

logger = logging.getLogger(__name__)


class AuthRepository:
    """Persist and retrieve UFC user authentication data."""

    async def authenticate_user(
        self,
        session: AsyncSession,
        *,
        email: str,
        password: str,
    ) -> Optional[Person]:
        """Return the :class:`Person` when credentials are valid."""

        try:
            result = await session.execute(select(Person).where(Person.email == email))
            person = result.scalars().first()
        except SQLAlchemyError as exc:  # pragma: no cover - defensive guard
            logger.exception("Failed to authenticate UFC user")
            raise DatabaseError(
                "Unable to authenticate user", operation="authenticate_user"
            ) from exc

        if person is None:
            return None

        password_bytes = password.encode("utf-8")
        stored_hash = person.password.encode("utf-8")
        if not bcrypt.checkpw(password_bytes, stored_hash):
            return None

        return person

    async def register_user(
        self,
        session: AsyncSession,
        *,
        account_name: str,
        email: str,
        password: str,
        lang: str | None = None,
        photo: str | None = None,
    ) -> Person:
        """Insert a new UFC user after hashing the supplied ``password``."""

        hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode(
            "utf-8"
        )

        person = Person(
            account_name=account_name,
            email=email,
            password=hashed_password,
        )
        if lang:
            person.lang = lang
        if photo:
            person.photo = photo

        try:
            session.add(person)
            await session.flush()
            logger.info("Registered UFC user", extra={"email": email})
            return person
        except IntegrityError as exc:
            logger.info("Duplicate UFC user registration attempted", extra={"email": email})
            raise DatabaseError(
                "User already exists", operation="register_user_duplicate"
            ) from exc
        except SQLAlchemyError as exc:  # pragma: no cover - defensive guard
            logger.exception("Failed to register UFC user")
            raise DatabaseError("Unable to register user", operation="register_user") from exc

    async def user_exists(self, session: AsyncSession, *, email: str) -> bool:
        """Return ``True`` when a user with ``email`` exists."""

        try:
            result = await session.execute(select(Person.id).where(Person.email == email))
            return result.scalar_one_or_none() is not None
        except SQLAlchemyError as exc:  # pragma: no cover - defensive guard
            logger.exception("Failed to determine if UFC user exists")
            raise DatabaseError("Unable to query user existence", operation="user_exists") from exc

    async def get_user_profile(
        self, session: AsyncSession, *, email: str
    ) -> Optional[Person]:
        """Return the :class:`Person` identified by ``email`` when present."""

        try:
            result = await session.execute(select(Person).where(Person.email == email))
            return result.scalars().first()
        except SQLAlchemyError as exc:  # pragma: no cover - defensive guard
            logger.exception("Failed to fetch UFC user profile")
            raise DatabaseError("Unable to fetch user profile", operation="get_user_profile") from exc


__all__ = ["AuthRepository"]
