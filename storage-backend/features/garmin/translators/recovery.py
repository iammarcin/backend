"""Translators for Garmin recovery-focused datasets."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from features.garmin.schemas.queries import GarminDataQuery

from .utils import coerce_date_key, iter_mappings, query_default_date


def translate_hrv(payload: Any, query: GarminDataQuery) -> Iterable[Mapping[str, Any]]:
    """Normalise HRV payloads into schema-aligned dictionaries."""

    records: list[dict[str, Any]] = []
    for entry in iter_mappings(payload):
        summary = entry.get("hrvSummary") if isinstance(entry.get("hrvSummary"), Mapping) else entry
        if not isinstance(summary, Mapping):
            continue

        calendar_source = (
            summary.get("calendarDate")
            or summary.get("calendar_date")
            or entry.get("calendarDate")
            or entry.get("calendar_date")
            or query_default_date(query)
        )
        calendar_date = coerce_date_key(calendar_source)
        if calendar_date is None:
            continue

        baseline = summary.get("baseline") if isinstance(summary.get("baseline"), Mapping) else {}
        record: dict[str, Any] = {
            "calendar_date": calendar_date,
            "hrv_weekly_avg": summary.get("weeklyAvg") or summary.get("weekly_avg"),
            "hrv_last_night_avg": summary.get("lastNightAvg") or summary.get("last_night_avg"),
            "hrv_status": summary.get("status") or summary.get("hrv_status"),
            "hrv_baseline_balanced_low": (
                baseline.get("balancedLow") if isinstance(baseline, Mapping) else None
            ),
            "hrv_baseline_balanced_upper": (
                baseline.get("balancedUpper") if isinstance(baseline, Mapping) else None
            ),
        }

        record = {key: value for key, value in record.items() if value is not None}
        records.append(record)

    return records


def translate_training_readiness(
    payload: Any, query: GarminDataQuery
) -> Iterable[Mapping[str, Any]]:
    """Normalise training readiness payloads."""

    records: list[dict[str, Any]] = []
    for entry in iter_mappings(payload):
        calendar_source = entry.get("calendarDate") or entry.get("calendar_date") or query_default_date(query)
        calendar_date = coerce_date_key(calendar_source)
        if calendar_date is None:
            continue

        record = {
            "calendar_date": calendar_date,
            "training_readiness_level": entry.get("level") or entry.get("training_readiness_level"),
            "training_readiness_score": entry.get("score") or entry.get("training_readiness_score"),
            "sleep_score": entry.get("sleepScore") or entry.get("sleep_score"),
            "sleep_score_factor_feedback": entry.get("sleepScoreFactorFeedback"),
            "recovery_time_factor_feedback": entry.get("recoveryTimeFactorFeedback"),
            "recovery_time": entry.get("recoveryTime"),
            "acute_load": entry.get("acuteLoad"),
            "hrv_weekly_average": entry.get("hrvWeeklyAverage"),
            "hrv_factor_feedback": entry.get("hrvFactorFeedback"),
            "stress_history_factor_feedback": entry.get("stressHistoryFactorFeedback"),
            "sleep_history_factor_feedback": entry.get("sleepHistoryFactorFeedback"),
        }
        records.append({key: value for key, value in record.items() if value is not None})

    return records
