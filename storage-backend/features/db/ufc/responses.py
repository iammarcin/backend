"""Utility helpers for building UFC error responses.

Each helper returns a :class:`~fastapi.responses.JSONResponse` configured with
the envelope schema used by the UFC feature, keeping the endpoint modules free
from repetitive boilerplate.
"""

from __future__ import annotations

import logging

from fastapi import status
from fastapi.responses import JSONResponse

from core.pydantic_schemas import error as api_error
from core.exceptions import AuthenticationError, ConfigurationError, DatabaseError, ServiceError, ValidationError

from .schemas import UfcErrorData, UfcErrorDetail

logger = logging.getLogger(__name__)


def validation_error_response(
    exc: ValidationError, *, status_code: int = status.HTTP_400_BAD_REQUEST
) -> JSONResponse:
    """Return a consistent validation error envelope."""

    detail = UfcErrorDetail(message=str(exc), field=getattr(exc, "field", None))
    payload = api_error(
        code=status_code,
        message="Validation error while processing UFC request",
        data=UfcErrorData(errors=[detail]).model_dump(),
    )
    return JSONResponse(status_code=status_code, content=payload)


def authentication_error_response(exc: AuthenticationError) -> JSONResponse:
    """Return a 401 response when credentials are invalid."""

    payload = api_error(
        code=status.HTTP_401_UNAUTHORIZED,
        message="Invalid credentials for UFC authentication",
        data=UfcErrorData(errors=[UfcErrorDetail(message=str(exc))]).model_dump(),
    )
    return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content=payload)


def conflict_error_response(exc: DatabaseError) -> JSONResponse:
    """Return a 409 response when registration encounters a duplicate."""

    payload = api_error(
        code=status.HTTP_409_CONFLICT,
        message=str(getattr(exc, "message", "Conflict while processing UFC request")),
        data=UfcErrorData(
            errors=[
                UfcErrorDetail(
                    message=str(exc),
                    field=getattr(exc, "operation", None),
                )
            ]
        ).model_dump(),
    )
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content=payload)


def database_error_response(exc: DatabaseError) -> JSONResponse:
    """Return a consistent database error envelope."""

    logger.error("Database error in UFC route", exc_info=exc)
    payload = api_error(
        code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message="Database error while processing UFC request",
        data=UfcErrorData(
            errors=[UfcErrorDetail(message=str(exc), field=getattr(exc, "operation", None))]
        ).model_dump(),
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=payload,
    )


def configuration_error_response(exc: ConfigurationError) -> JSONResponse:
    """Return a response when infrastructure configuration is missing."""

    payload = api_error(
        code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message="Configuration error while processing UFC request",
        data=UfcErrorData(
            errors=[UfcErrorDetail(message=str(exc), field=getattr(exc, "key", None))]
        ).model_dump(),
    )
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=payload)


def service_error_response(exc: ServiceError) -> JSONResponse:
    """Return a response when a service layer operation fails."""

    payload = api_error(
        code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message="Service error while processing UFC request",
        data=UfcErrorData(errors=[UfcErrorDetail(message=str(exc))]).model_dump(),
    )
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=payload)


__all__ = [
    "authentication_error_response",
    "configuration_error_response",
    "conflict_error_response",
    "database_error_response",
    "service_error_response",
    "validation_error_response",
]

