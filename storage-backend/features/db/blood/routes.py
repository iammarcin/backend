"""HTTP routing for the Blood feature."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.pydantic_schemas import error as api_error, ok as api_ok
from core.exceptions import DatabaseError

from .dependencies import get_blood_service, get_blood_session
from .schemas import BloodTestItem, BloodTestListResponse
from .schemas.requests import BloodLegacyRequest, BloodTestListQueryParams
from .schemas.responses import (
    BloodErrorData,
    BloodErrorDetail,
    BloodErrorResponse,
    BloodTestListEnvelope,
)
from .service import BloodService

logger = logging.getLogger(__name__)

if hasattr(status, "HTTP_422_UNPROCESSABLE_CONTENT"):
    HTTP_422_UNPROCESSABLE_STATUS = status.HTTP_422_UNPROCESSABLE_CONTENT
else:  # pragma: no cover - exercised in environments with older Starlette
    HTTP_422_UNPROCESSABLE_STATUS = getattr(status, "HTTP_422_UNPROCESSABLE_ENTITY", 422)


router = APIRouter(prefix="/api/v1/blood", tags=["Blood"])


@router.get(
    "/tests",
    summary="List blood test records",
    description="Retrieve blood test history with optional date and category filters.",
    response_model=BloodTestListEnvelope,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": BloodErrorResponse},
        HTTP_422_UNPROCESSABLE_STATUS: {"model": BloodErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": BloodErrorResponse},
    },
)
async def list_blood_tests_endpoint(
    query: BloodTestListQueryParams = Depends(),
    session: AsyncSession = Depends(get_blood_session),
    service: BloodService = Depends(get_blood_service),
):
    """Return blood tests serialised for API consumers."""

    filters = query.to_filters()
    try:
        response = await service.list_tests(session, filters=filters)
    except DatabaseError as exc:
        return _database_error_response(exc)

    payload = response.model_dump(mode="json")
    message = (
        "Retrieved blood tests"
        if filters is None
        else "Retrieved blood tests with applied filters"
    )

    meta: dict[str, Any] = {"total_count": response.total_count}
    if response.latest_test_date:
        meta["latest_test_date"] = response.latest_test_date.isoformat()
    if filters:
        meta["filters"] = filters.model_dump(mode="json", exclude_none=True)

    logger.info(
        "Blood tests requested",
        extra={
            "filters": meta.get("filters"),
            "total_count": response.total_count,
        },
    )
    return api_ok(message=message, data=payload, meta=meta)


@router.post(
    "/legacy",
    summary="Legacy compatibility endpoint for blood data",
    description="Maintain the MediaModel action contract for existing automation.",
    responses={
        status.HTTP_200_OK: {"description": "Legacy blood response"},
        status.HTTP_400_BAD_REQUEST: {"description": "Unsupported action"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Server error"},
    },
)
async def blood_legacy_endpoint(
    request: BloodLegacyRequest,
    session: AsyncSession = Depends(get_blood_session),
    service: BloodService = Depends(get_blood_service),
):
    """Bridge legacy MediaModel payloads to the new blood service layer."""

    logger.info(
        "Blood legacy request received",
        extra={"action": request.action, "customer_id": request.customer_id},
    )

    if not request.is_supported_action():
        logger.warning(
            "Unsupported blood legacy action",
            extra={"action": request.action},
        )
        return _legacy_error(
            status.HTTP_400_BAD_REQUEST,
            f"Unsupported blood action: {request.action}",
        )

    try:
        response = await service.list_tests(session)
    except DatabaseError as exc:
        logger.error(
            "Database error while processing legacy blood request",
            exc_info=exc,
        )
        return _legacy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))

    legacy_payload = _serialise_legacy_items(response)
    return _legacy_success(legacy_payload)


def _database_error_response(exc: DatabaseError) -> JSONResponse:
    logger.error("Database error retrieving blood tests", exc_info=exc)
    detail = BloodErrorDetail(message=str(exc))
    payload = api_error(
        code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message="Database error while retrieving blood tests",
        data=BloodErrorData(errors=[detail]).model_dump(),
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=payload,
    )


def _serialise_legacy_items(response: BloodTestListResponse) -> list[dict[str, Any]]:
    """Convert service response items into the legacy JSON contract."""

    items: list[dict[str, Any]] = []
    for item in response.items:
        items.append(_legacy_item(item))
    return items


def _legacy_item(item: BloodTestItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "test_date": item.test_date.isoformat(),
        "result_value": item.result_value,
        "result_unit": item.result_unit,
        "reference_range": item.reference_range,
        "category": item.category,
        "test_name": item.test_name,
        "short_explanation": item.short_explanation,
        "long_explanation": item.long_explanation,
    }


def _legacy_success(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "code": status.HTTP_200_OK,
        "success": True,
        "message": {"status": "completed", "result": items},
    }


def _legacy_error(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "code": status_code,
            "success": False,
            "message": {"status": "fail", "result": message},
        },
    )


__all__ = ["router"]
