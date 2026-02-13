"""Authentication endpoints for the UFC feature.

These handlers expose login, registration, user existence, and profile
retrieval flows. They wrap service layer responses with the shared envelope
format and translate common failure modes to structured error payloads.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import AuthenticationError, DatabaseError, ValidationError
from core.pydantic_schemas import ok as api_ok

from .dependencies import get_ufc_service, get_ufc_session
from .responses import (
    authentication_error_response,
    conflict_error_response,
    database_error_response,
    validation_error_response,
)
from .schemas import (
    AuthEnvelope,
    AuthLoginRequest,
    AuthRegistrationRequest,
    RegistrationEnvelope,
    UfcErrorResponse,
    UserExistsEnvelope,
    UserProfileEnvelope,
)
from .service import UfcService

logger = logging.getLogger(__name__)


def register_auth_routes(router: APIRouter) -> None:
    """Attach authentication-related endpoints to ``router``."""

    @router.post(
        "/auth/login",
        summary="Authenticate a UFC user",
        response_model=AuthEnvelope,
        responses={
            status.HTTP_400_BAD_REQUEST: {"model": UfcErrorResponse},
            status.HTTP_401_UNAUTHORIZED: {"model": UfcErrorResponse},
            status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": UfcErrorResponse},
        },
    )
    async def authenticate_user_endpoint(
        payload: AuthLoginRequest,
        session: AsyncSession = Depends(get_ufc_session),
        service: UfcService = Depends(get_ufc_service),
    ):
        """Authenticate a UFC user and return their profile."""

        logger.info("Authenticate UFC user request", extra={"email": payload.email})

        try:
            result = await service.authenticate_user(session, payload)
        except ValidationError as exc:
            return validation_error_response(exc)
        except AuthenticationError as exc:
            return authentication_error_response(exc)
        except DatabaseError as exc:
            return database_error_response(exc)

        data = result.model_dump(mode="json", by_alias=True, exclude_none=True)
        meta = {"tokenProvided": bool(result.token)}
        return api_ok(message=result.message, data=data, meta=meta)

    @router.post(
        "/auth/register",
        summary="Register a UFC user",
        response_model=RegistrationEnvelope,
        responses={
            status.HTTP_400_BAD_REQUEST: {"model": UfcErrorResponse},
            status.HTTP_409_CONFLICT: {"model": UfcErrorResponse},
            status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": UfcErrorResponse},
        },
    )
    async def register_user_endpoint(
        payload: AuthRegistrationRequest,
        session: AsyncSession = Depends(get_ufc_session),
        service: UfcService = Depends(get_ufc_service),
    ):
        """Register a new UFC user account."""

        logger.info("Register UFC user request", extra={"email": payload.email})

        try:
            result = await service.register_user(session, payload)
        except ValidationError as exc:
            return validation_error_response(exc)
        except DatabaseError as exc:
            if getattr(exc, "operation", None) == "register_user_duplicate":
                return conflict_error_response(exc)
            return database_error_response(exc)

        data = result.model_dump(mode="json", by_alias=True, exclude_none=True)
        meta = {"userId": result.user_id}
        return api_ok(message=result.message, data=data, meta=meta)

    @router.get(
        "/users/{email}/exists",
        summary="Check if a UFC user exists",
        response_model=UserExistsEnvelope,
        responses={
            status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": UfcErrorResponse},
        },
    )
    async def user_exists_endpoint(
        email: str,
        session: AsyncSession = Depends(get_ufc_session),
        service: UfcService = Depends(get_ufc_service),
    ):
        """Return a boolean describing whether ``email`` is registered."""

        logger.info("Check UFC user existence", extra={"email": email})

        try:
            result = await service.user_exists(session, email)
        except DatabaseError as exc:
            return database_error_response(exc)

        data = result.model_dump(mode="json", by_alias=True, exclude_none=True)
        return api_ok(message=result.message, data=data)

    @router.get(
        "/users/{email}",
        summary="Retrieve a UFC user profile",
        response_model=UserProfileEnvelope,
        responses={
            status.HTTP_404_NOT_FOUND: {"model": UfcErrorResponse},
            status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": UfcErrorResponse},
        },
    )
    async def get_user_profile_endpoint(
        email: str,
        session: AsyncSession = Depends(get_ufc_session),
        service: UfcService = Depends(get_ufc_service),
    ):
        """Return the UFC user profile associated with ``email``."""

        logger.info("Get UFC user profile", extra={"email": email})

        try:
            profile = await service.get_user_profile(session, email)
        except ValidationError as exc:
            return validation_error_response(exc, status_code=status.HTTP_404_NOT_FOUND)
        except DatabaseError as exc:
            return database_error_response(exc)

        data = profile.model_dump(mode="json", by_alias=True, exclude_none=True)
        meta = {"email": profile.email}
        return api_ok(message="User profile retrieved", data=data, meta=meta)


__all__ = ["register_auth_routes"]

