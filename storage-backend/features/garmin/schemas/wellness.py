"""Request models covering Garmin wellness metrics such as summaries and readiness."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Mapping, Sequence

from pydantic import Field, field_validator

from .base import GarminRequest, as_midnight, normalise_iterable, parse_date
from .internal import (
    BodyCompositionRecord,
    DailyHealthEventRecord,
    EnduranceScoreRecord,
    FitnessAgeRecord,
    HRVRecord,
    TrainingReadinessRecord,
    TrainingStatusRecord,
    UserSummaryRecord,
)


class _DateCoercionMixin:
    """Provide shared ``calendar_date`` coercion behaviour."""

    _coerce_date = field_validator("calendar_date", mode="before")(parse_date)


class UserSummaryRequest(_DateCoercionMixin, GarminRequest):
    """Daily Garmin activity summary metrics for a user."""

    calendar_date: date = Field(alias="calendarDate")
    total_kilocalories: float | None = None
    active_kilocalories: float | None = None
    bmr_kilocalories: float | None = None
    total_steps: int | None = None
    total_distance_meters: int | None = None
    min_heart_rate: int | None = None
    max_heart_rate: int | None = None
    resting_heart_rate: int | None = None
    last_seven_days_avg_resting_heart_rate: int | None = None
    vigorous_intensity_minutes: int | None = None
    moderate_intensity_minutes: int | None = None
    average_stress_level: int | None = None
    total_stress_duration: int | None = None
    stress_duration: int | None = None
    uncategorized_stress_duration: int | None = None
    rest_stress_duration: int | None = None
    low_stress_duration: int | None = None
    activity_stress_duration: int | None = None
    medium_stress_duration: int | None = None
    high_stress_duration: int | None = None
    stress_qualifier: str | None = None
    body_battery_charged_value: int | None = None
    body_battery_drained_value: int | None = None
    body_battery_highest_value: int | None = None
    body_battery_lowest_value: int | None = None
    body_battery_most_recent_value: int | None = None
    avg_waking_respiration_value: float | None = None
    highest_respiration_value: float | None = None
    lowest_respiration_value: float | None = None
    latest_respiration_value: float | None = None

    def to_internal(self) -> UserSummaryRecord:
        """Convert the request payload into the storage DTO."""

        data = self.model_dump(by_alias=False, exclude_none=True)
        data["calendar_date"] = as_midnight(self.calendar_date)
        return UserSummaryRecord(data)  # type: ignore[arg-type]


class BodyCompositionRequest(_DateCoercionMixin, GarminRequest):
    """Body composition metrics such as BMI and muscle mass."""

    calendar_date: date = Field(alias="calendarDate")
    weight: float | None = None
    bmi: float | None = None
    body_fat_mass: float | None = None
    body_fat_percentage: float | None = None
    body_water_mass: float | None = None
    body_water_percentage: float | None = None
    bone_mass: float | None = None
    bone_mass_percentage: float | None = None
    muscle_mass: float | None = None
    muscle_mass_percentage: float | None = None
    visceral_fat: float | None = None
    basal_metabolic_rate: int | None = None

    def to_internal(self) -> BodyCompositionRecord:
        """Convert the request payload into the storage DTO."""

        data = self.model_dump(by_alias=False, exclude_none=True)
        data["calendar_date"] = as_midnight(self.calendar_date)
        return BodyCompositionRecord(data)  # type: ignore[arg-type]


class HRVRequest(_DateCoercionMixin, GarminRequest):
    """Heart rate variability request payload."""

    calendar_date: date = Field(alias="calendarDate")
    hrv_weekly_avg: int | None = None
    hrv_last_night_avg: int | None = None
    hrv_status: str | None = None
    hrv_baseline_balanced_low: int | None = None
    hrv_baseline_balanced_upper: int | None = None

    def to_internal(self) -> HRVRecord:
        """Convert the request payload into the storage DTO."""

        data = self.model_dump(by_alias=False, exclude_none=True)
        data["calendar_date"] = as_midnight(self.calendar_date)
        return HRVRecord(data)  # type: ignore[arg-type]


class TrainingReadinessRequest(_DateCoercionMixin, GarminRequest):
    """Daily training readiness metrics reported by Garmin."""

    calendar_date: date = Field(alias="calendarDate")
    training_readiness_level: str | None = Field(default=None, alias="level")
    training_readiness_score: int | None = Field(default=None, alias="score", ge=0, le=100)
    sleep_score: int | None = None
    sleep_score_factor_feedback: str | None = None
    recovery_time_factor_feedback: str | None = None
    recovery_time: int | None = None
    acute_load: int | None = None
    hrv_weekly_average: int | None = None
    hrv_factor_feedback: str | None = None
    stress_history_factor_feedback: str | None = None
    sleep_history_factor_feedback: str | None = None

    def to_internal(self) -> TrainingReadinessRecord:
        """Convert the request payload into the storage DTO."""

        data = self.model_dump(by_alias=False, exclude_none=True)
        data["calendar_date"] = as_midnight(self.calendar_date)
        return TrainingReadinessRecord(data)  # type: ignore[arg-type]


class EnduranceScoreRequest(_DateCoercionMixin, GarminRequest):
    """Capture Garmin endurance score data and contributors."""

    calendar_date: date = Field(alias="calendarDate")
    endurance_score: int | None = Field(default=None, ge=0)
    endurance_score_classification: int | None = None
    endurance_score_classification_lower_limit_intermediate: int | None = None
    endurance_score_classification_lower_limit_trained: int | None = None
    endurance_score_classification_lower_limit_well_trained: int | None = None
    endurance_score_classification_lower_limit_expert: int | None = None
    endurance_score_classification_lower_limit_superior: int | None = None
    endurance_score_classification_lower_limit_elite: int | None = None
    endurance_score_contributors: Sequence[Mapping[str, Any]] | Mapping[str, Any] | None = None

    def to_internal(self) -> EnduranceScoreRecord:
        """Convert the request payload into the storage DTO."""

        data = self.model_dump(by_alias=False, exclude_none=True)
        data["calendar_date"] = as_midnight(self.calendar_date)
        if "endurance_score_contributors" in data:
            raw = data["endurance_score_contributors"]
            if isinstance(raw, Mapping):
                data["endurance_score_contributors"] = dict(raw)
            elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
                data["endurance_score_contributors"] = normalise_iterable(raw)
        return EnduranceScoreRecord(data)  # type: ignore[arg-type]


class TrainingStatusRequest(_DateCoercionMixin, GarminRequest):
    """Training status and VO2 max metrics."""

    calendar_date: date = Field(alias="calendarDate")
    daily_training_load_acute: int | None = None
    daily_training_load_acute_feedback: str | None = None
    daily_training_load_chronic: float | None = None
    min_training_load_chronic: float | None = None
    max_training_load_chronic: float | None = None
    vo2_max_precise_value: float | None = None
    vo2_max_feedback: str | None = None
    monthly_load_anaerobic: float | None = None
    monthly_load_aerobic_high: float | None = None
    monthly_load_aerobic_low: float | None = None
    monthly_load_aerobic_low_target_min: float | None = None
    monthly_load_aerobic_low_target_max: float | None = None
    monthly_load_aerobic_high_target_min: float | None = None
    monthly_load_aerobic_high_target_max: float | None = None
    monthly_load_anaerobic_target_min: float | None = None
    monthly_load_anaerobic_target_max: float | None = None
    training_balance_feedback_phrase: str | None = None

    def to_internal(self) -> TrainingStatusRecord:
        """Convert the request payload into the storage DTO."""

        data = self.model_dump(by_alias=False, exclude_none=True)
        data["calendar_date"] = as_midnight(self.calendar_date)
        return TrainingStatusRecord(data)  # type: ignore[arg-type]


class FitnessAgeRequest(_DateCoercionMixin, GarminRequest):
    """Represent Garmin's calculated fitness age values."""

    calendar_date: date = Field(alias="calendarDate")
    chronological_age: int | None = None
    fitness_age: float | None = None
    body_fat_value: float | None = None
    vigorous_days_avg_value: float | None = None
    rhr_value: int | None = None
    vigorous_minutes_avg_value: float | None = None

    def to_internal(self) -> FitnessAgeRecord:
        """Convert the request payload into the storage DTO."""

        data = self.model_dump(by_alias=False, exclude_none=True)
        data["calendar_date"] = as_midnight(self.calendar_date)
        return FitnessAgeRecord(data)  # type: ignore[arg-type]


class DailyHealthEventsRequest(_DateCoercionMixin, GarminRequest):
    """Daily health event timestamps such as meals or screen time."""

    calendar_date: date = Field(alias="calendarDate")
    last_meal_time: datetime | None = None
    last_drink_time: datetime | None = None
    last_screen_time: datetime | None = None

    @field_validator("last_meal_time", "last_drink_time", "last_screen_time", mode="after")
    def _strip_tz(cls, value: datetime | None) -> datetime | None:
        """Drop timezone information to align with naive DB columns."""

        if value is None:
            return None
        return value.replace(tzinfo=None)

    def to_internal(self) -> DailyHealthEventRecord:
        """Convert the request payload into the storage DTO."""

        data = self.model_dump(by_alias=False, exclude_none=True)
        data["calendar_date"] = as_midnight(self.calendar_date)
        return DailyHealthEventRecord(data)  # type: ignore[arg-type]


__all__ = [
    "BodyCompositionRequest",
    "DailyHealthEventsRequest",
    "EnduranceScoreRequest",
    "FitnessAgeRequest",
    "HRVRequest",
    "TrainingReadinessRequest",
    "TrainingStatusRequest",
    "UserSummaryRequest",
]
