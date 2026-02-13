"""Garmin dataset fetcher implementations shared by the provider service."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Iterable, Mapping, TYPE_CHECKING

from core.exceptions import ProviderError
from features.garmin.schemas.queries import GarminDataQuery

if TYPE_CHECKING:
    from features.garmin.dataset_registry import FetchWindow, GarminDatasetContext


logger = logging.getLogger(__name__)


def _is_not_found_error(exc: ProviderError) -> bool:
    """Return ``True`` when Garmin raised a 404/Not Found style error."""

    message = str(exc).lower()
    return "404" in message or "not found" in message


def fetch_sleep(context: "GarminDatasetContext", window: "FetchWindow", query: GarminDataQuery) -> Any:
    display_name = window.display_name or ""
    return context.client.fetch_sleep(display_name=display_name, start=window.start, end=window.end)


def fetch_summary(context: "GarminDatasetContext", window: "FetchWindow", query: GarminDataQuery) -> Any:
    display_name = window.display_name or ""
    return context.client.fetch_user_summary(display_name=display_name, start=window.start, end=window.end)


def fetch_body_composition(
    context: "GarminDatasetContext", window: "FetchWindow", query: GarminDataQuery
) -> Mapping[str, Any]:
    garmin_payload = context.client.fetch_body_composition(start=window.start, end=window.end)
    withings_payload: list[dict[str, Any]] | None = None
    if context.withings:
        try:
            withings_payload = context.withings.fetch_body_composition(start=window.start, end=window.end)
        except Exception as exc:  # pragma: no cover - logged for observability
            logger.warning(
                "Withings body composition fetch failed",
                extra={"start": window.start.isoformat(), "end": window.end.isoformat()},
                exc_info=exc,
            )
    return {"garmin": garmin_payload, "withings": withings_payload}


def fetch_hrv(context: "GarminDatasetContext", window: "FetchWindow", query: GarminDataQuery) -> list[Mapping[str, Any]]:
    results: list[Mapping[str, Any]] = []
    for day in _date_range(window.start, window.end):
        payload = context.client.fetch_hrv(target_date=day)
        if payload:
            results.append(payload)
    return results


def fetch_training_readiness(
    context: "GarminDatasetContext", window: "FetchWindow", query: GarminDataQuery
) -> list[Mapping[str, Any]]:
    results: list[Mapping[str, Any]] = []
    for day in _date_range(window.start, window.end):
        payload = context.client.fetch_training_readiness(target_date=day)
        if payload:
            if isinstance(payload, list):
                results.extend(payload)
            else:
                results.append(payload)
    return results


def fetch_endurance_score(context: "GarminDatasetContext", window: "FetchWindow", query: GarminDataQuery) -> Any:
    return context.client.fetch_endurance_score(start=window.start, end=window.end)


def fetch_training_status(
    context: "GarminDatasetContext", window: "FetchWindow", query: GarminDataQuery
) -> list[Mapping[str, Any]]:
    results: list[Mapping[str, Any]] = []
    for day in _date_range(window.start, window.end):
        payload = context.client.fetch_training_status(target_date=day)
        if payload:
            results.append(payload)
    return results


def fetch_training_load_balance(
    context: "GarminDatasetContext", window: "FetchWindow", query: GarminDataQuery
) -> list[Mapping[str, Any]]:
    """Fetch training load balance metrics for each day in the window."""

    results: list[Mapping[str, Any]] = []
    for day in _date_range(window.start, window.end):
        payload = context.client.fetch_training_load_balance(target_date=day)
        if payload:
            results.append(payload)
    return results


def fetch_fitness_age(context: "GarminDatasetContext", window: "FetchWindow", query: GarminDataQuery) -> list[Mapping[str, Any]]:
    results: list[Mapping[str, Any]] = []
    for day in _date_range(window.start, window.end):
        payload = context.client.fetch_fitness_age(target_date=day)
        if payload:
            results.append(payload)
    return results


def _merge_activity_payloads(
    summary: Mapping[str, Any] | None,
    detail: Mapping[str, Any] | None,
) -> Mapping[str, Any]:
    """Merge summary and detail payloads preferring rich detail metrics."""

    if detail is None and summary is None:
        return {}

    # Start with detail data (contains zones/metrics) and overlay summary fallbacks.
    merged: dict[str, Any] = {}
    if isinstance(detail, Mapping):
        merged.update(detail)

    if isinstance(summary, Mapping):
        for key, value in summary.items():
            merged.setdefault(key, value)

        # Ensure summaryDTO from summary remains available when detail payload omitted it.
        summary_dto = summary.get("summaryDTO")
        if summary_dto and "summaryDTO" not in merged:
            merged["summaryDTO"] = summary_dto

    # Promote core fields from nested summary DTOs when the merged payload lacks them.
    def _promote_from(source: Mapping[str, Any] | None) -> None:
        if not isinstance(source, Mapping):
            return
        dto = source.get("summaryDTO") if isinstance(source.get("summaryDTO"), Mapping) else None
        candidates = [source, dto]
        for candidate in candidates:
            if not isinstance(candidate, Mapping):
                continue
            activity_name = candidate.get("activityName")
            if activity_name and not merged.get("activityName"):
                merged["activityName"] = activity_name
            activity_id = candidate.get("activityId")
            if activity_id and not merged.get("activityId"):
                merged["activityId"] = activity_id
            calendar_date = candidate.get("calendarDate")
            if calendar_date and not merged.get("calendarDate"):
                merged["calendarDate"] = calendar_date

    _promote_from(detail)
    _promote_from(summary)

    return merged


def fetch_activity(context: "GarminDatasetContext", window: "FetchWindow", query: GarminDataQuery) -> Any:
    if query.activity_id is not None:
        payload = context.client.fetch_activity_detail(query.activity_id)
        return [] if payload is None else [payload]

    summaries = context.client.fetch_activities(
        start=window.start,
        end=window.end,
        limit=query.limit,
        offset=query.offset,
    )

    enriched: list[Mapping[str, Any]] = []
    for summary in summaries:
        if not isinstance(summary, Mapping):
            continue

        activity_id = summary.get("activityId") or summary.get("activity_id")
        detail_payload = None
        activity_id_int = None
        if isinstance(activity_id, int):
            activity_id_int = activity_id
        elif isinstance(activity_id, str) and activity_id.isdigit():
            activity_id_int = int(activity_id)

        if activity_id_int is not None:
            detail_payload = context.client.fetch_activity_detail(activity_id_int)

        enriched.append(_merge_activity_payloads(summary, detail_payload))

    return enriched


def fetch_activity_gps(context: "GarminDatasetContext", window: "FetchWindow", query: GarminDataQuery) -> Any:
    if query.activity_id is None:
        raise ProviderError(
            "activity_id is required for activity GPS dataset",
            provider="garmin",
        )

    payload: Mapping[str, Any] | None = None
    try:
        payload = context.client.fetch_activity_gps(query.activity_id)
    except ProviderError as exc:
        if _is_not_found_error(exc):
            logger.info(
                "Garmin GPS endpoint returned no data; falling back to activity details",
                extra={"activity_id": query.activity_id},
            )
        else:
            raise

    detail_payload = context.client.fetch_activity_detail(query.activity_id)

    if not payload and not detail_payload:
        logger.info(
            "No Garmin GPS detail available for activity", extra={"activity_id": query.activity_id}
        )
        return []

    merged_payload = _merge_activity_payloads(payload, detail_payload)
    if not merged_payload:
        return []

    return [merged_payload]


def fetch_daily_health_events(
    context: "GarminDatasetContext", window: "FetchWindow", query: GarminDataQuery
) -> list[Mapping[str, Any]]:
    if not window.display_name:
        raise ProviderError(
            "Garmin display name required for daily health events",
            provider="garmin",
        )
    results: list[Mapping[str, Any]] = []
    for day in _date_range(window.start, window.end):
        payload = context.client.fetch_daily_health_events(target_date=day, display_name=window.display_name)
        if payload:
            if isinstance(payload, list):
                results.extend(payload)
            else:
                results.append(payload)
    return results


def fetch_max_metrics(context: "GarminDatasetContext", window: "FetchWindow", query: GarminDataQuery) -> list[Mapping[str, Any]]:
    """Fetch VO2 max metrics with monthly granularity for the window period.

    This method returns monthly VO2 max values from Garmin. These values are typically merged
    with training_status records to enrich daily training load data with VO2 max feedback.
    """
    payload = context.client.fetch_max_metrics(start=window.start, end=window.end)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, Mapping):
        return [payload]
    return []


def _date_range(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


__all__ = [
    "fetch_activity",
    "fetch_activity_gps",
    "fetch_body_composition",
    "fetch_daily_health_events",
    "fetch_endurance_score",
    "fetch_fitness_age",
    "fetch_hrv",
    "fetch_max_metrics",
    "fetch_sleep",
    "fetch_summary",
    "fetch_training_readiness",
    "fetch_training_status",
    "fetch_training_load_balance",
]
