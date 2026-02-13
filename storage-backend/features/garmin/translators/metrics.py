"""Fitness age and VO2 max metrics translators for Garmin performance data."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from features.garmin.schemas.queries import GarminDataQuery

from .utils import coerce_date_key, deep_get, extract_date, iter_mappings, query_default_date


def translate_fitness_age(payload: Any, query: GarminDataQuery) -> Iterable[Mapping[str, Any]]:
    """Normalise fitness age payloads."""

    records: list[dict[str, Any]] = []
    for entry in iter_mappings(payload):
        calendar_source = (
            entry.get("calendarDate")
            or entry.get("calendar_date")
            or extract_date(entry.get("lastUpdated"))
            or query_default_date(query)
        )
        calendar_date = coerce_date_key(calendar_source)
        if calendar_date is None:
            continue

        record = {
            "calendar_date": calendar_date,
            "chronological_age": entry.get("chronologicalAge"),
            "fitness_age": entry.get("fitnessAge"),
            "body_fat_value": deep_get(entry.get("components"), "bodyFat", "value"),
            "vigorous_days_avg_value": deep_get(entry.get("components"), "vigorousDaysAvg", "value"),
            "rhr_value": deep_get(entry.get("components"), "rhr", "value"),
            "vigorous_minutes_avg_value": deep_get(entry.get("components"), "vigorousMinutesAvg", "value"),
        }
        records.append({key: value for key, value in record.items() if value is not None})

    return records


def translate_max_metrics(payload: Any, query: GarminDataQuery) -> Iterable[Mapping[str, Any]]:
    """Normalise VO2 max metrics payloads for merging with training status.

    VO2 max metrics are returned as monthly entries from Garmin's maxmet endpoint.
    These are translated into training_status records where they enrich daily records
    with VO2 max feedback and precise values.

    When a target_date is provided, this function selects the latest VO2 max entry
    that occurs on or before the target_date and returns it with the target_date
    as the calendar_date. This allows VO2 max data to be backfilled for the specific
    date when used in cascade workflows (e.g., training_status → max_metrics).

    When target_date is not provided, all monthly entries are normalized and returned
    as-is (backward compatibility mode).
    """

    records: list[dict[str, Any]] = []

    # Collect all normalized VO2 max entries
    all_entries: list[tuple[Any, Mapping[str, Any]]] = []
    for entry in iter_mappings(payload):
        if not isinstance(entry, Mapping):
            continue

        # Extract the generic VO2 data which contains vo2MaxPreciseValue
        vo2_record: Mapping[str, Any] | None = None
        if isinstance(entry.get("generic"), Mapping):
            vo2_record = entry.get("generic")
        elif isinstance(entry.get("vo2MaxPreciseValue"), (int, float, str)):
            vo2_record = entry

        if not vo2_record:
            continue

        calendar_source = vo2_record.get("calendarDate") or vo2_record.get("calendar_date") or query_default_date(query)
        calendar_date = coerce_date_key(calendar_source)
        if calendar_date is None:
            continue

        vo2_value = deep_get(vo2_record, "vo2MaxPreciseValue")
        vo2_feedback = deep_get(vo2_record, "fitnessAgeDescription")

        if vo2_value is not None:
            all_entries.append((calendar_date, {
                "vo2_max_precise_value": vo2_value,
                "vo2_max_feedback": vo2_feedback,
            }))

    # If target_date is provided, select the latest VO2 max before/on that date
    if query.target_date:
        # Filter to entries on or before target_date
        valid_entries = [
            (cal_date, data) for cal_date, data in all_entries
            if cal_date <= query.target_date
        ]

        if valid_entries:
            # Sort by calendar_date descending and take the first (most recent)
            valid_entries.sort(key=lambda x: x[0], reverse=True)
            latest_date, latest_data = valid_entries[0]

            # Return with target_date as the calendar_date
            record = {
                "calendar_date": query.target_date,
                **latest_data,
            }
            records.append({key: value for key, value in record.items() if value is not None})
    else:
        # No target_date: return all entries with their original calendar dates
        for calendar_date, data in all_entries:
            record = {
                "calendar_date": calendar_date,
                **data,
            }
            records.append({key: value for key, value in record.items() if value is not None})

    return records
