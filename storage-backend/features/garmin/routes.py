"""Garmin provider API routes."""

from __future__ import annotations

from typing import Any, Iterable, Sequence

from fastapi import APIRouter, Body, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ValidationError
from core.pydantic_schemas import ok as api_ok
from features.db.garmin.service import GarminService

from .dependencies import (
    get_garmin_provider_service,
    get_garmin_service,
    get_garmin_session,
)
from .routes_common import garmin_disabled_error, handle_errors
from .routes_datasets import register_dataset_routes
from .schemas.activity import ActivityRequest
from .schemas.queries import GarminDataQuery
from .service import GarminProviderService

router = APIRouter(prefix="/api/v1/garmin", tags=["Garmin"])


@router.get("/status", summary="Return Garmin provider status")
async def garmin_status(
    service: GarminProviderService = Depends(get_garmin_provider_service),
) -> JSONResponse:
    metadata = service.status()
    payload = api_ok(message="Garmin provider status", data=metadata)
    return JSONResponse(status_code=status.HTTP_200_OK, content=payload)


@router.post(
    "/activities",
    summary="Persist enriched Garmin activities",
    response_description="Persistence outcome for posted activities",
)
async def save_activities(
    payload: Sequence[dict[str, Any]] | dict[str, Any] = Body(...),
    customer_id: int = Query(..., alias="customer_id", ge=1),
    garmin_service: GarminService = Depends(get_garmin_service),
    session: AsyncSession | None = Depends(get_garmin_session),
) -> JSONResponse:
    """Persist one or more Garmin activities supplied by the caller."""

    if session is None:
        return handle_errors(garmin_disabled_error())

    try:
        entries: Sequence[dict[str, Any]]
        if isinstance(payload, dict):
            entries = (payload,)
        else:
            entries = list(payload)

        if not entries:
            raise ValidationError("At least one activity payload is required")

        requests = [ActivityRequest.model_validate(entry) for entry in entries]
        results = [
            await garmin_service.ingest_activity(session, request, customer_id) for request in requests
        ]
    except Exception as exc:  # noqa: BLE001 - delegated to handler
        return handle_errors(exc)

    data = {
        "ingested": [result.to_dict() for result in results],
        "count": len(results),
    }
    meta = {"customer_id": customer_id}
    message = "Persisted Garmin activity" if len(results) == 1 else "Persisted Garmin activities"
    body = api_ok(message=message, data=data, meta=meta)
    return JSONResponse(status_code=status.HTTP_200_OK, content=body)


@router.get(
    "/analysis/overview",
    summary="Return aggregated Garmin datasets",
    response_description="Combined datasets for analysis dashboards",
)
async def garmin_analysis_overview(
    query: GarminDataQuery = Depends(),
    customer_id: int = Query(..., alias="customer_id", ge=1),
    include_optimized: bool = Query(True, alias="include_optimized"),
    datasets: list[str] | None = Query(None),
    service: GarminProviderService = Depends(get_garmin_provider_service),
    garmin_service: GarminService = Depends(get_garmin_service),
    session: AsyncSession | None = Depends(get_garmin_session),
) -> JSONResponse:
    if session is None:
        return handle_errors(garmin_disabled_error())

    try:
        keys: Iterable[str] | None = datasets
        payload = await garmin_service.fetch_analysis(
            session,
            query,
            customer_id,
            datasets=keys,
            include_optimized=include_optimized,
        )
    except Exception as exc:  # noqa: BLE001 - delegated to handler
        return handle_errors(exc)

    meta = {
        "customer_id": customer_id,
        "query": query.model_dump(mode="json", exclude_none=True),
        "datasets": list(keys) if keys else garmin_service.default_analysis_datasets(),
        "include_optimized": include_optimized,
    }
    message = "Retrieved Garmin analysis overview"
    body = api_ok(message=message, data=payload, meta=meta)
    return JSONResponse(status_code=status.HTTP_200_OK, content=body)


@router.get(
    "/activity/{activity_id}",
    summary="Fetch activity GPS metrics and details",
    response_description="Detailed GPS metrics for a specific activity",
)
async def get_activity_detail(
    activity_id: int,
    service: GarminProviderService = Depends(get_garmin_provider_service),
) -> JSONResponse:
    """Fetch detailed GPS metrics for a specific Garmin activity.

    This endpoint returns raw activity detail data from Garmin Connect API.
    Includes GPS metrics, elevation, heart rate, cadence, power, etc.

    Args:
        activity_id: Garmin activity identifier
        service: Injected Garmin provider service

    Returns:
        JSONResponse with activity detail payload
    """

    try:
        # Call client directly - no dataset translation needed
        data = service._context.client.fetch_activity_detail(activity_id)

        if data is None:
            return handle_errors(
                ValidationError(f"Activity {activity_id} not found or has no detail data")
            )

        message = f"Retrieved activity {activity_id} details"
        payload = api_ok(message=message, data=data)
        return JSONResponse(status_code=status.HTTP_200_OK, content=payload)

    except Exception as exc:  # noqa: BLE001 - delegated to handler
        return handle_errors(exc)


@router.get(
    "/activity/{activity_id}/weather",
    summary="Fetch activity weather conditions",
    response_description="Weather data for a specific activity",
)
async def get_activity_weather(
    activity_id: int,
    service: GarminProviderService = Depends(get_garmin_provider_service),
) -> JSONResponse:
    """Fetch weather conditions during a specific Garmin activity.

    Returns temperature, humidity, wind, precipitation, and weather type.

    Args:
        activity_id: Garmin activity identifier
        service: Injected Garmin provider service

    Returns:
        JSONResponse with weather payload
    """

    try:
        data = service._context.client.fetch_activity_weather(activity_id)

        if data is None:
            return handle_errors(
                ValidationError(f"Activity {activity_id} not found or has no weather data")
            )

        message = f"Retrieved weather for activity {activity_id}"
        payload = api_ok(message=message, data=data)
        return JSONResponse(status_code=status.HTTP_200_OK, content=payload)

    except Exception as exc:  # noqa: BLE001 - delegated to handler
        return handle_errors(exc)


@router.get(
    "/activity/{activity_id}/hr-zones",
    summary="Fetch activity heart rate zones",
    response_description="Heart rate time-in-zones for a specific activity",
)
async def get_activity_hr_zones(
    activity_id: int,
    service: GarminProviderService = Depends(get_garmin_provider_service),
) -> JSONResponse:
    """Fetch heart rate zone distribution for a specific Garmin activity.

    Returns time spent in each heart rate zone (zone0-zone5) with boundaries.

    Args:
        activity_id: Garmin activity identifier
        service: Injected Garmin provider service

    Returns:
        JSONResponse with HR zone payload
    """

    try:
        data = service._context.client.fetch_activity_hr_zones(activity_id)

        if data is None:
            return handle_errors(
                ValidationError(f"Activity {activity_id} not found or has no HR zone data")
            )

        message = f"Retrieved HR zones for activity {activity_id}"
        payload = api_ok(message=message, data=data)
        return JSONResponse(status_code=status.HTTP_200_OK, content=payload)

    except Exception as exc:  # noqa: BLE001 - delegated to handler
        return handle_errors(exc)


_REGISTERED_DATASET_ENDPOINTS = register_dataset_routes(router)


__all__ = [
    "router",
    "garmin_status",
    "save_activities",
    "garmin_analysis_overview",
    "get_activity_detail",
    "get_activity_weather",
    "get_activity_hr_zones",
    *_REGISTERED_DATASET_ENDPOINTS,
]
