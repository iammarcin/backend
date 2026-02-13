"""Authentication orchestration for the UFC service layer."""

from __future__ import annotations

import logging
from typing import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import AuthenticationError, ValidationError
from ..repositories import AuthRepository
from ..schemas import AuthResult, RegistrationResult, UserExistsResult, UserProfile
from ..schemas.requests import AuthLoginRequest, AuthRegistrationRequest
from .validators import normalise_email, validate_password

logger = logging.getLogger(__name__)


class AuthCoordinator:
    """Handle user authentication and registration flows."""

    def __init__(
        self,
        repository: AuthRepository,
        token_provider: Callable[[], str | None],
        *,
        min_password_length: int,
    ) -> None:
        self._repository = repository
        self._token_provider = token_provider
        self._min_password_length = min_password_length

    async def authenticate_user(
        self,
        session: AsyncSession,
        payload: AuthLoginRequest,
    ) -> AuthResult:
        """Authenticate a UFC user and return profile plus token."""

        password = validate_password(payload.password, min_length=self._min_password_length)
        email = normalise_email(payload.email)

        person = await self._repository.authenticate_user(
            session,
            email=email,
            password=password,
        )
        if person is None:
            raise AuthenticationError("Invalid email or password")

        profile = UserProfile.model_validate(person)
        token = self._token_provider()
        logger.info("User authenticated", extra={"email": profile.email})

        return AuthResult(
            status="authenticated",
            message="User authenticated",
            token=token,
            user=profile,
        )

    async def register_user(
        self,
        session: AsyncSession,
        payload: AuthRegistrationRequest,
    ) -> RegistrationResult:
        """Register a new UFC user account."""

        password = validate_password(payload.password, min_length=self._min_password_length)
        email = normalise_email(payload.email)

        person = await self._repository.register_user(
            session,
            account_name=payload.account_name,
            email=email,
            password=password,
            lang=payload.lang,
            photo=payload.photo,
        )

        logger.info("User registered", extra={"user_id": person.id, "email": person.email})
        return RegistrationResult(
            status="registered",
            message="User registered",
            user_id=person.id,
            email=person.email,
            accountName=person.account_name,
        )

    async def user_exists(self, session: AsyncSession, email: str) -> UserExistsResult:
        """Return whether a UFC user exists for ``email``."""

        normalised = normalise_email(email)
        exists = await self._repository.user_exists(session, email=normalised)
        message = "User exists" if exists else "User not found"
        return UserExistsResult(email=normalised, exists=exists, message=message)

    async def get_user_profile(self, session: AsyncSession, email: str) -> UserProfile:
        """Return the user profile associated with ``email`` or raise if absent."""

        normalised = normalise_email(email)
        person = await self._repository.get_user_profile(session, email=normalised)
        if person is None:
            raise ValidationError("User not found", field="email")
        logger.debug("Resolved user profile", extra={"email": normalised})
        return UserProfile.model_validate(person)


__all__ = ["AuthCoordinator"]
