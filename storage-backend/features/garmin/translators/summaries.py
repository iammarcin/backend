"""Translation helpers for simple Garmin daily summary datasets."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from features.garmin.schemas.queries import GarminDataQuery

from .utils import coerce_date_key, iter_mappings, query_default_date


def translate_sleep(payload: Any, query: GarminDataQuery) -> Iterable[Mapping[str, Any]]:
    """Normalise the sleep dataset to an iterable of mapping objects."""

    records: list[dict[str, Any]] = []
    for entry in iter_mappings(payload):
        daily_sleep = entry.get("dailySleepDTO")
        if not isinstance(daily_sleep, Mapping):
            daily_sleep = entry

        calendar_source = (
            daily_sleep.get("calendarDate")
            or entry.get("calendarDate")
            or query_default_date(query)
        )
        calendar_date = coerce_date_key(calendar_source)
        if calendar_date is None:
            continue

        record = dict(entry)
        record["calendarDate"] = calendar_date
        records.append(record)

    return records


def translate_summary(payload: Any, query: GarminDataQuery) -> Iterable[Mapping[str, Any]]:
    """Normalise the daily summary dataset to an iterable of dictionaries."""

    records: list[dict[str, Any]] = []
    for entry in iter_mappings(payload):
        summary_section = None
        if isinstance(entry, Mapping):
            for key in (
                "summary",
                "wellnessSummary",
                "userSummary",
                "dailySummaryDTO",
                "summaryDTO",
            ):
                candidate = entry.get(key)
                if isinstance(candidate, Mapping):
                    summary_section = candidate
                    break

        calendar_source = None
        if isinstance(summary_section, Mapping):
            calendar_source = summary_section.get("calendarDate") or summary_section.get(
                "calendar_date"
            )
        if calendar_source is None and isinstance(entry, Mapping):
            calendar_source = entry.get("calendarDate") or entry.get("calendar_date")
        if calendar_source is None:
            calendar_source = query_default_date(query)

        calendar_date = coerce_date_key(calendar_source)
        if calendar_date is None:
            continue

        record = dict(entry)
        record["calendarDate"] = calendar_date
        records.append(record)

    return records
