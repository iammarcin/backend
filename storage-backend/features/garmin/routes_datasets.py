"""Dataset-oriented Garmin API routes."""

from __future__ import annotations

from typing import Any, Callable, TypedDict

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ValidationError

from .dependencies import get_garmin_provider_service, get_garmin_session
from .routes_common import dataset_response, handle_errors
from .schemas.queries import GarminDataQuery
from .service import GarminProviderService


class DatasetRouteConfig(TypedDict):
    """Typed holder for Garmin dataset route metadata."""

    name: str
    path: str
    dataset: str
    summary: str
    response_description: str
    require_activity_id: bool
    validation_error: str | None


DEFAULT_QUERY_DEPENDENCIES: dict[str, Any] = {
    "query": Depends(),
    "customer_id": Query(
        ..., alias="customer_id", ge=1, description="Customer identifier"
    ),
    "save_to_db": Query(
        None,
        alias="save_to_db",
        description="Persist fetched data before returning",
    ),
    "service": Depends(get_garmin_provider_service),
    "session": Depends(get_garmin_session),
}


DATASET_ROUTES: tuple[DatasetRouteConfig, ...] = (
    DatasetRouteConfig(
        name="garmin_sleep_endpoint",
        path="/sleep",
        dataset="sleep",
        summary="Fetch Garmin sleep data",
        response_description="Sleep payloads returned from Garmin Connect",
        require_activity_id=False,
        validation_error=None,
    ),
    DatasetRouteConfig(
        name="garmin_summary_endpoint",
        path="/summary",
        dataset="summary",
        summary="Fetch Garmin user summary data",
        response_description="Daily summaries returned from Garmin Connect",
        require_activity_id=False,
        validation_error=None,
    ),
    DatasetRouteConfig(
        name="garmin_body_composition_endpoint",
        path="/body-composition",
        dataset="body_composition",
        summary="Fetch Garmin + Withings body composition data",
        response_description="Body composition metrics enriched with Withings data when available",
        require_activity_id=False,
        validation_error=None,
    ),
    DatasetRouteConfig(
        name="garmin_hrv_endpoint",
        path="/hrv",
        dataset="hrv",
        summary="Fetch Garmin HRV data",
        response_description="Heart rate variability summary data from Garmin Connect",
        require_activity_id=False,
        validation_error=None,
    ),
    DatasetRouteConfig(
        name="garmin_training_readiness_endpoint",
        path="/training-readiness",
        dataset="training_readiness",
        summary="Fetch Garmin training readiness data",
        response_description="Training readiness factors and scores",
        require_activity_id=False,
        validation_error=None,
    ),
    DatasetRouteConfig(
        name="garmin_endurance_score_endpoint",
        path="/endurance-score",
        dataset="training_endurance",
        summary="Fetch Garmin endurance score data",
        response_description="Endurance score classifications and contributors",
        require_activity_id=False,
        validation_error=None,
    ),
    DatasetRouteConfig(
        name="garmin_training_status_endpoint",
        path="/training-status",
        dataset="training_status",
        summary="Fetch Garmin training status data",
        response_description="Training load balance, VO2 metrics, and status feedback",
        require_activity_id=False,
        validation_error=None,
    ),
    DatasetRouteConfig(
        name="garmin_training_load_balance_endpoint",
        path="/training-load-balance",
        dataset="training_load_balance",
        summary="Fetch Garmin training load balance data",
        response_description="Monthly aerobic/anaerobic load balance metrics",
        require_activity_id=False,
        validation_error=None,
    ),
    DatasetRouteConfig(
        name="garmin_fitness_age_endpoint",
        path="/fitness-age",
        dataset="training_fitness_age",
        summary="Fetch Garmin fitness age data",
        response_description="Fitness age calculations and contributing metrics",
        require_activity_id=False,
        validation_error=None,
    ),
    DatasetRouteConfig(
        name="garmin_activity_endpoint",
        path="/activities",
        dataset="activity",
        summary="Fetch Garmin activity summaries",
        response_description="Activity summaries returned from Garmin Connect",
        require_activity_id=False,
        validation_error=None,
    ),
    DatasetRouteConfig(
        name="garmin_activity_gps_endpoint",
        path="/activity-gps",
        dataset="activity_gps",
        summary="Fetch Garmin activity GPS data",
        response_description="High resolution GPS tracks for a Garmin activity",
        require_activity_id=True,
        validation_error="activity_id is required for activity GPS requests",
    ),
    DatasetRouteConfig(
        name="garmin_daily_health_events_endpoint",
        path="/daily-health-events",
        dataset="daily_health_events",
        summary="Fetch Garmin daily health events",
        response_description="Daily health event timestamps from Garmin Connect",
        require_activity_id=False,
        validation_error=None,
    ),
    DatasetRouteConfig(
        name="garmin_max_metrics_endpoint",
        path="/max-metrics",
        dataset="max_metrics",
        summary="Fetch Garmin VO2 max metrics",
        response_description="Monthly VO2 max metrics and feedback for training status enrichment",
        require_activity_id=False,
        validation_error=None,
    ),
)


def register_dataset_routes(router: APIRouter) -> list[str]:
    """Register dataset routes on the provided router and return their function names."""

    registered: list[str] = []
    for config in DATASET_ROUTES:
        endpoint = _create_dataset_endpoint(config)
        router.get(
            config["path"],
            summary=config["summary"],
            response_description=config["response_description"],
        )(endpoint)
        registered.append(endpoint.__name__)
    return registered


def _create_dataset_endpoint(config: DatasetRouteConfig) -> Callable[..., JSONResponse]:
    dataset_key = config["dataset"]
    require_activity_id = config["require_activity_id"]
    validation_error = config["validation_error"]

    async def endpoint(
        query: GarminDataQuery = DEFAULT_QUERY_DEPENDENCIES["query"],
        customer_id: int = DEFAULT_QUERY_DEPENDENCIES["customer_id"],
        save_to_db: bool | None = DEFAULT_QUERY_DEPENDENCIES["save_to_db"],
        service: GarminProviderService = DEFAULT_QUERY_DEPENDENCIES["service"],
        session: AsyncSession | None = DEFAULT_QUERY_DEPENDENCIES["session"],
        *,
        _dataset: str = dataset_key,
        _require_activity_id: bool = require_activity_id,
        _validation_error: str | None = validation_error,
    ) -> JSONResponse:
        if _require_activity_id and query.activity_id is None:
            return handle_errors(ValidationError(_validation_error or "activity_id is required"))
        return await dataset_response(_dataset, query, customer_id, save_to_db, service, session)

    endpoint.__name__ = config["name"]
    endpoint.__qualname__ = config["name"]
    return endpoint


__all__ = ["register_dataset_routes"]

