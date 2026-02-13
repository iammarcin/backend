"""Utilities shared across the chat history route modules."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, TypeVar

import logging
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from core.exceptions import AuthenticationError, DatabaseError, ValidationError
from core.pydantic_schemas import error, ok


logger = logging.getLogger(__name__)

if hasattr(status, "HTTP_422_UNPROCESSABLE_CONTENT"):
    HTTP_422_UNPROCESSABLE_STATUS = status.HTTP_422_UNPROCESSABLE_CONTENT
else:  # pragma: no cover - exercised in environments with older Starlette
    HTTP_422_UNPROCESSABLE_STATUS = getattr(status, "HTTP_422_UNPROCESSABLE_ENTITY", 422)


history_router = APIRouter(prefix="/api/v1/chat", tags=["Chat History"])

T = TypeVar("T")
Formatter = Callable[[T], Dict[str, Any]]


def handle_service_error(exc: Exception) -> JSONResponse:
    """Convert domain service exceptions into JSON API responses."""

    if isinstance(exc, ValidationError):
        logger.warning(
            "Chat request validation failed: %s (field=%s)",
            exc.message,
            exc.field,
        )
        data: dict[str, Any] | None = None
        if exc.field:
            data = {"field": exc.field}
        return JSONResponse(
            status_code=HTTP_422_UNPROCESSABLE_STATUS,
            content=error(422, exc.message, data=data),
        )
    if isinstance(exc, AuthenticationError):
        logger.warning("Chat authentication failure")
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=error(401, str(exc)),
        )
    if isinstance(exc, DatabaseError):
        logger.error(
            "Chat database error during %s: %s",
            exc.operation,
            exc.message,
        )
        not_found_operations = {
            "fetch_session",
            "remove_session",
            "update_session",
            "delete_prompt",
            "update_message",
        }
        status_code = (
            status.HTTP_404_NOT_FOUND
            if exc.operation in not_found_operations or "not found" in exc.message.lower()
            else status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        return JSONResponse(status_code=status_code, content=error(status_code, exc.message))
    logger.exception("Unexpected chat service error")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error(500, "Internal server error"),
    )


async def execute_service_call(
    operation: Callable[[], Awaitable[T]],
    *,
    success_message: str,
    formatter: Formatter[T],
) -> Dict[str, Any] | JSONResponse:
    """Execute a service call and wrap the result with a standard payload."""

    try:
        result = await operation()
    except Exception as exc:  # pragma: no cover - delegated to handler
        return handle_service_error(exc)
    return ok(success_message, data=formatter(result))


__all__ = [
    "execute_service_call",
    "handle_service_error",
    "history_router",
    "logger",
]

