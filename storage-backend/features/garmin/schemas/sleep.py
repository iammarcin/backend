"""Validation helpers for Garmin sleep payload ingestion."""

from __future__ import annotations

from datetime import date
from typing import Any, Mapping, Sequence

from pydantic import Field, field_validator

from features.db.garmin.utils import get_local_offset, prepare_garmin_sleep_data

from .base import GarminRequest, as_midnight, format_offset, normalise_iterable, parse_date
from .internal import SleepRecord


SLEEP_FIELD_MAPPING: dict[str, str] = {
    # Basic sleep metrics
    "sleepTimeSeconds": "sleep_time_seconds",
    "napTimeSeconds": "nap_time_seconds",
    "deepSleepSeconds": "deep_sleep_seconds",
    "lightSleepSeconds": "light_sleep_seconds",
    "remSleepSeconds": "rem_sleep_seconds",
    "awakeSleepSeconds": "awake_sleep_seconds",

    # Respiration metrics (API uses non-prefixed keys)
    "averageRespirationValue": "sleep_average_respiration_value",
    "lowestRespirationValue": "sleep_lowest_respiration_value",
    "highestRespirationValue": "sleep_highest_respiration_value",
    "awakeCount": "sleep_awake_count",

    # Sleep stress and insight feedback
    "avgSleepStress": "avg_sleep_stress",
    "sleepScoreFeedback": "sleep_score_feedback",
    "sleepScoreInsight": "sleep_score_insight",
    "sleepScorePersonalizedInsight": "sleep_score_personalized_insight",
}
"""Field name mapping from Garmin's dailySleepDTO keys to repository expectations."""


class SleepIngestRequest(GarminRequest):
    """Validate and normalise Garmin sleep payloads before persistence."""

    calendar_date: date = Field(alias="calendarDate")
    daily_sleep_dto: Mapping[str, Any] = Field(alias="dailySleepDTO")
    daily_nap_dtos: Sequence[Mapping[str, Any]] = Field(default_factory=list, alias="dailyNapDTOS")
    sleep_levels: Sequence[Mapping[str, Any]] = Field(default_factory=list)
    sleep_heart_rate: Sequence[Mapping[str, Any]] = Field(default_factory=list)
    hrv_data: Sequence[Mapping[str, Any]] = Field(default_factory=list, alias="hrvData")
    sleep_stress: Sequence[Mapping[str, Any]] = Field(default_factory=list)
    avg_overnight_hrv: float | None = Field(default=None, alias="avgOvernightHrv")
    resting_heart_rate: int | None = Field(default=None, alias="restingHeartRate")
    body_battery_change: int | None = Field(default=None, alias="bodyBatteryChange")
    restless_moments_count: int | None = Field(default=None, alias="restlessMomentsCount")

    _coerce_date = field_validator("calendar_date", mode="before")(parse_date)

    def to_internal(self) -> SleepRecord:
        """Return a repository-ready representation of the payload."""

        base_payload: dict[str, Any] = {
            "dailySleepDTO": dict(self.daily_sleep_dto),
            "dailyNapDTOS": normalise_iterable(self.daily_nap_dtos),
            "sleepLevels": normalise_iterable(self.sleep_levels),
            "sleepHeartRate": normalise_iterable(self.sleep_heart_rate),
            "sleepStress": normalise_iterable(self.sleep_stress),
            "hrvData": normalise_iterable(self.hrv_data),
        }
        main_sleep = base_payload["dailySleepDTO"]
        offset = get_local_offset(
            main_sleep.get("sleepStartTimestampGMT"),
            main_sleep.get("sleepStartTimestampLocal"),
        )
        (
            sleep_start,
            sleep_end,
            sleep_start_gmt,
            sleep_end_gmt,
            nap_data,
            sleep_levels_data,
            sleep_heart_rate_data,
            sleep_hrv_data,
            sleep_stress_data,
        ) = prepare_garmin_sleep_data(base_payload, offset)

        payload: SleepRecord = {
            "calendar_date": as_midnight(self.calendar_date),
            "time_offset": format_offset(offset),
            "sleep_start": sleep_start,
            "sleep_end": sleep_end,
            "sleep_start_gmt": sleep_start_gmt,
            "sleep_end_gmt": sleep_end_gmt,
            "nap_data": nap_data,
            "sleep_levels_data": sleep_levels_data,
            "sleep_heart_rate_data": sleep_heart_rate_data,
            "sleep_hrv_data": sleep_hrv_data,
            "sleep_stress_data": sleep_stress_data,
        }

        for source, target in SLEEP_FIELD_MAPPING.items():
            if source in main_sleep:
                payload[target] = main_sleep.get(source)

        sleep_scores = main_sleep.get("sleepScores")
        if isinstance(sleep_scores, Mapping):
            overall = sleep_scores.get("overall", {})
            if overall:
                payload["sleep_overall_score_value"] = overall.get("value")
                payload["sleep_overall_score_qualifier"] = overall.get("qualifierKey")

            total_duration = sleep_scores.get("totalDuration", {})
            if total_duration:
                payload["sleep_total_duration_qualifier"] = total_duration.get("qualifierKey")

            stress = sleep_scores.get("stress", {})
            if stress:
                payload["sleep_stress_qualifier"] = stress.get("qualifierKey")

            awake_count = sleep_scores.get("awakeCount", {})
            if awake_count:
                payload["sleep_awake_count_qualifier"] = awake_count.get("qualifierKey")

            rem_percentage = sleep_scores.get("remPercentage", {})
            if rem_percentage:
                payload["sleep_rem_percentage_value"] = rem_percentage.get("value")
                payload["sleep_rem_percentage_qualifier"] = rem_percentage.get("qualifierKey")
                payload["sleep_rem_optimal_start"] = rem_percentage.get("optimalStart")
                payload["sleep_rem_optimal_end"] = rem_percentage.get("optimalEnd")

            restlessness = sleep_scores.get("restlessness", {})
            if restlessness:
                payload["sleep_restlessness_qualifier"] = restlessness.get("qualifierKey")
                payload["sleep_restlessness_optimal_start"] = restlessness.get("optimalStart")
                payload["sleep_restlessness_optimal_end"] = restlessness.get("optimalEnd")

            light_percentage = sleep_scores.get("lightPercentage", {})
            if light_percentage:
                payload["sleep_light_percentage_value"] = light_percentage.get("value")
                payload["sleep_light_percentage_qualifier"] = light_percentage.get("qualifierKey")
                payload["sleep_light_optimal_start"] = light_percentage.get("optimalStart")
                payload["sleep_light_optimal_end"] = light_percentage.get("optimalEnd")

            deep_percentage = sleep_scores.get("deepPercentage", {})
            if deep_percentage:
                payload["sleep_deep_percentage_value"] = deep_percentage.get("value")
                payload["sleep_deep_percentage_qualifier"] = deep_percentage.get("qualifierKey")
                payload["sleep_deep_optimal_start"] = deep_percentage.get("optimalStart")
                payload["sleep_deep_optimal_end"] = deep_percentage.get("optimalEnd")

        if self.avg_overnight_hrv is not None:
            payload["sleep_avg_overnight_hrv"] = self.avg_overnight_hrv
        if self.resting_heart_rate is not None:
            payload["sleep_resting_heart_rate"] = self.resting_heart_rate
        if self.body_battery_change is not None:
            payload["sleep_body_battery_change"] = self.body_battery_change
        if self.restless_moments_count is not None:
            payload["sleep_restless_moments_count"] = self.restless_moments_count

        return payload


__all__ = ["SleepIngestRequest", "SLEEP_FIELD_MAPPING"]
