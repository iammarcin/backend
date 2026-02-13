"""Standard API response envelope helpers."""

from __future__ import annotations

from typing import Any, Dict, Generic, Mapping, Optional, TypeVar, Union

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


MessageType = Union[str, Mapping[str, Any]]


class ApiResponse(BaseModel, Generic[T]):
    """Canonical API response envelope shared across services."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    code: int = Field(..., description="HTTP-like status code signalling success or failure")
    success: bool = Field(..., description="Indicates whether the operation completed successfully")
    message: MessageType = Field(
        ...,
        description="Human readable summary or structured payload for UI clients",
    )
    data: Optional[T] = Field(None, description="Optional domain payload")
    meta: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional metadata for pagination, tracing, or analytics",
    )


def api_response(
    *,
    code: int = 200,
    message: MessageType,
    data: T | None = None,
    meta: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Return a serialisable API envelope with a consistent schema."""

    envelope = ApiResponse[T](
        code=code,
        success=code < 400,
        message=message,
        data=data,
        meta=meta,
    )
    return envelope.model_dump(by_alias=True)


def ok(message: str, data: T | None = None, meta: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Shortcut for successful responses."""

    return api_response(code=200, message=message, data=data, meta=meta)


def error(
    code: int,
    message: str,
    data: Any | None = None,
    meta: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Shortcut for error responses with caller-provided status codes."""

    if code < 400:
        raise ValueError("Error responses must use an error HTTP status code (>= 400)")
    return api_response(code=code, message=message, data=data, meta=meta)


__all__ = ["ApiResponse", "api_response", "ok", "error"]
