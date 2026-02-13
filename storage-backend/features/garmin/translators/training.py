"""Training status and load balance translators for Garmin performance data."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from features.garmin.schemas.queries import GarminDataQuery

from .utils import coerce_date_key, deep_get, first_mapping, iter_mappings, query_default_date


def translate_training_status(payload: Any, query: GarminDataQuery) -> Iterable[Mapping[str, Any]]:
    """Normalise training status payloads including load balance and VO2 metrics."""

    records: list[dict[str, Any]] = []
    for entry in iter_mappings(payload):
        # Training status data lives at the top level in real responses, but keep nested fallback.
        status_map: Any = None
        if isinstance(entry, Mapping):
            status_map = entry.get("latestTrainingStatusData")
        if not status_map:
            status_section = entry.get("mostRecentTrainingStatus")
            if isinstance(status_section, Mapping):
                status_map = status_section.get("latestTrainingStatusData")
        status_record = first_mapping(status_map)

        # Training load balance DTO follows the same pattern (top-level first, nested fallback).
        load_map: Any = None
        if isinstance(entry, Mapping):
            load_map = entry.get("metricsTrainingLoadBalanceDTOMap")
        if not load_map:
            load_section = entry.get("mostRecentTrainingLoadBalance")
            if isinstance(load_section, Mapping):
                load_map = load_section.get("metricsTrainingLoadBalanceDTOMap")
        load_record = first_mapping(load_map)

        # VO2 data may be present directly, under a generic key, or nested under mostRecentVO2Max.
        vo2_record: Mapping[str, Any] | None = None
        if isinstance(entry, Mapping):
            if isinstance(entry.get("vo2MaxPreciseValue"), (int, float, str)) or "vo2MaxPreciseValue" in entry:
                vo2_record = entry
            elif isinstance(entry.get("generic"), Mapping):
                vo2_record = entry.get("generic")
            else:
                vo2_section = entry.get("mostRecentVO2Max")
                if isinstance(vo2_section, Mapping):
                    generic_vo2 = vo2_section.get("generic")
                    vo2_record = generic_vo2 if isinstance(generic_vo2, Mapping) else vo2_section

        acute_dto = status_record.get("acuteTrainingLoadDTO") if isinstance(status_record, Mapping) else None

        calendar_source = None
        if isinstance(status_record, Mapping):
            calendar_source = status_record.get("calendarDate") or status_record.get("calendar_date")
        if calendar_source is None and isinstance(load_record, Mapping):
            calendar_source = load_record.get("calendarDate") or load_record.get("calendar_date")
        if calendar_source is None and isinstance(vo2_record, Mapping):
            calendar_source = vo2_record.get("calendarDate") or vo2_record.get("calendar_date")
        if calendar_source is None:
            calendar_source = query_default_date(query)

        calendar_date = coerce_date_key(calendar_source)
        if calendar_date is None:
            continue

        record: dict[str, Any] = {
            "calendar_date": calendar_date,
            "daily_training_load_acute": deep_get(acute_dto, "dailyTrainingLoadAcute"),
            "daily_training_load_chronic": deep_get(acute_dto, "dailyTrainingLoadChronic"),
            "daily_training_load_acute_feedback": deep_get(acute_dto, "acwrStatus"),
            "min_training_load_chronic": deep_get(acute_dto, "minTrainingLoadChronic"),
            "max_training_load_chronic": deep_get(acute_dto, "maxTrainingLoadChronic"),
            "monthly_load_anaerobic": deep_get(load_record, "monthlyLoadAnaerobic"),
            "monthly_load_aerobic_high": deep_get(load_record, "monthlyLoadAerobicHigh"),
            "monthly_load_aerobic_low": deep_get(load_record, "monthlyLoadAerobicLow"),
            "monthly_load_aerobic_low_target_min": deep_get(
                load_record, "monthlyLoadAerobicLowTargetMin"
            ),
            "monthly_load_aerobic_low_target_max": deep_get(
                load_record, "monthlyLoadAerobicLowTargetMax"
            ),
            "monthly_load_aerobic_high_target_min": deep_get(
                load_record, "monthlyLoadAerobicHighTargetMin"
            ),
            "monthly_load_aerobic_high_target_max": deep_get(
                load_record, "monthlyLoadAerobicHighTargetMax"
            ),
            "monthly_load_anaerobic_target_min": deep_get(load_record, "monthlyLoadAnaerobicTargetMin"),
            "monthly_load_anaerobic_target_max": deep_get(load_record, "monthlyLoadAnaerobicTargetMax"),
            "training_balance_feedback_phrase": deep_get(load_record, "trainingBalanceFeedbackPhrase")
            or deep_get(status_record, "trainingStatusFeedbackPhrase"),
            "vo2_max_precise_value": deep_get(vo2_record, "vo2MaxPreciseValue"),
            "vo2_max_feedback": deep_get(status_record, "trainingStatusFeedbackPhrase")
            or deep_get(vo2_record, "fitnessAgeDescription"),
        }

        records.append({key: value for key, value in record.items() if value is not None})

    return records


def translate_training_load_balance(payload: Any, query: GarminDataQuery) -> Iterable[Mapping[str, Any]]:
    """Normalise training load balance payloads into training status records."""

    records: list[dict[str, Any]] = []
    for entry in iter_mappings(payload):
        load_map: Any = None
        if isinstance(entry, Mapping):
            load_map = entry.get("metricsTrainingLoadBalanceDTOMap")
        if not load_map:
            load_section = entry.get("mostRecentTrainingLoadBalance")
            if isinstance(load_section, Mapping):
                load_map = load_section.get("metricsTrainingLoadBalanceDTOMap")

        load_record = first_mapping(load_map)

        calendar_source = None
        if isinstance(load_record, Mapping):
            calendar_source = load_record.get("calendarDate") or load_record.get("calendar_date")
        if calendar_source is None:
            calendar_source = query_default_date(query)

        calendar_date = coerce_date_key(calendar_source)
        if calendar_date is None:
            continue

        record: dict[str, Any] = {
            "calendar_date": calendar_date,
            "monthly_load_anaerobic": deep_get(load_record, "monthlyLoadAnaerobic"),
            "monthly_load_aerobic_high": deep_get(load_record, "monthlyLoadAerobicHigh"),
            "monthly_load_aerobic_low": deep_get(load_record, "monthlyLoadAerobicLow"),
            "monthly_load_aerobic_low_target_min": deep_get(
                load_record, "monthlyLoadAerobicLowTargetMin"
            ),
            "monthly_load_aerobic_low_target_max": deep_get(
                load_record, "monthlyLoadAerobicLowTargetMax"
            ),
            "monthly_load_aerobic_high_target_min": deep_get(
                load_record, "monthlyLoadAerobicHighTargetMin"
            ),
            "monthly_load_aerobic_high_target_max": deep_get(
                load_record, "monthlyLoadAerobicHighTargetMax"
            ),
            "monthly_load_anaerobic_target_min": deep_get(load_record, "monthlyLoadAnaerobicTargetMin"),
            "monthly_load_anaerobic_target_max": deep_get(load_record, "monthlyLoadAnaerobicTargetMax"),
            "training_balance_feedback_phrase": deep_get(load_record, "trainingBalanceFeedbackPhrase"),
        }

        records.append({key: value for key, value in record.items() if value is not None})

    return records
