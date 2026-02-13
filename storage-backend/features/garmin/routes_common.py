"""Shared helpers for Garmin API routes."""

from __future__ import annotations

import logging

from fastapi import status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ConfigurationError, ProviderError, ValidationError
from core.pydantic_schemas import error as api_error, ok as api_ok

from .schemas.queries import GarminDataQuery
from .service import DatasetResult, GarminProviderService

GARMIN_DISABLED_MESSAGE = "Garmin features are disabled. Contact administrator."


def garmin_disabled_error() -> ConfigurationError:
    """Return a reusable configuration error for disabled Garmin features."""

    return ConfigurationError(GARMIN_DISABLED_MESSAGE, key="GARMIN_ENABLED")

logger = logging.getLogger(__name__)


def handle_errors(exc: Exception) -> JSONResponse:
    """Normalize Garmin provider errors to API responses."""

    if isinstance(exc, ConfigurationError):
        is_disabled = getattr(exc, "key", None) == "GARMIN_ENABLED"
        status_code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if is_disabled
            else status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        log_method = logger.warning if is_disabled else logger.error
        log_method(
            "Garmin configuration error: %s",
            str(exc),
            exc_info=None if is_disabled else exc,
            extra={
                "error_type": "ConfigurationError",
                "key": getattr(exc, "key", None),
            },
        )
        payload = api_error(
            code=status_code,
            message=str(exc),
            data={"key": exc.key} if getattr(exc, "key", None) else None,
        )
        return JSONResponse(status_code=status_code, content=payload)

    if isinstance(exc, ValidationError):
        logger.warning(
            "Garmin payload validation failed: %s",
            str(exc),
            exc_info=exc,
            extra={"error_type": "ValidationError"},
        )
        payload = api_error(code=status.HTTP_422_UNPROCESSABLE_ENTITY, message=str(exc))
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=payload)

    if isinstance(exc, ProviderError):
        logger.error(
            "Garmin provider error: %s",
            str(exc),
            exc_info=exc,
            extra={"error_type": "ProviderError", "provider": getattr(exc, "provider", None)},
        )
        payload = api_error(code=status.HTTP_502_BAD_GATEWAY, message=str(exc))
        return JSONResponse(status_code=status.HTTP_502_BAD_GATEWAY, content=payload)

    logger.exception(
        "Unhandled Garmin route error: %s (%s)",
        str(exc),
        type(exc).__name__,
        extra={"error_type": type(exc).__name__},
    )
    payload = api_error(
        code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message=f"Garmin request failed: {str(exc)}",
    )
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=payload)


async def dataset_response(
    dataset: str,
    query: GarminDataQuery,
    customer_id: int,
    save_to_db: bool | None,
    service: GarminProviderService,
    session: AsyncSession | None,
) -> JSONResponse:
    """Execute a dataset request and convert the result to the API response format."""

    if session is None:
        return handle_errors(garmin_disabled_error())

    # Log the dataset request for debugging
    logger.info(
        "Fetching Garmin dataset",
        extra={
            "dataset": dataset,
            "customer_id": customer_id,
            "start_date": query.start_date.isoformat() if query.start_date else None,
            "end_date": query.end_date.isoformat() if query.end_date else None,
            "save_to_db": save_to_db,
        },
    )

    try:
        result = await service.fetch_dataset(
            dataset,
            query,
            customer_id=customer_id,
            save_to_db=save_to_db,
            session=session,
        )
    except Exception as exc:  # noqa: BLE001 - delegated to handler
        return handle_errors(exc)

    data, meta = result.to_payload()
    meta.update(
        {
            "customer_id": customer_id,
            "query": query.model_dump(mode="json", exclude_none=True),
        }
    )
    message = dataset_message(dataset, result)
    payload = api_ok(message=message, data=data, meta=meta)

    # Log the successful result
    logger.info(
        "Garmin dataset retrieved",
        extra={
            "dataset": dataset,
            "customer_id": customer_id,
            "items_count": len(data) if isinstance(data, list) else 1,
            "saved": result.saved,
        },
    )

    return JSONResponse(status_code=status.HTTP_200_OK, content=payload)


def dataset_message(dataset: str, result: DatasetResult) -> str:
    """Build a human-readable dataset retrieval message."""

    label = dataset.replace("_", " ")
    if result.saved:
        return f"Retrieved Garmin {label} data (persisted)"
    return f"Retrieved Garmin {label} data"


__all__ = [
    "GARMIN_DISABLED_MESSAGE",
    "garmin_disabled_error",
    "dataset_message",
    "dataset_response",
    "handle_errors",
]

