"""Internal data structures passed from services to repositories."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, NotRequired, TypedDict


class SleepRecord(TypedDict, total=False):
    """Normalised Garmin sleep payload ready for persistence."""

    calendar_date: date
    time_offset: NotRequired[str | None]
    sleep_time_seconds: NotRequired[int | None]
    sleep_start: NotRequired[str | None]
    sleep_end: NotRequired[str | None]
    sleep_start_gmt: NotRequired[str | None]
    sleep_end_gmt: NotRequired[str | None]
    nap_time_seconds: NotRequired[int | None]
    nap_data: NotRequired[list[dict[str, Any]] | None]
    deep_sleep_seconds: NotRequired[int | None]
    light_sleep_seconds: NotRequired[int | None]
    rem_sleep_seconds: NotRequired[int | None]
    awake_sleep_seconds: NotRequired[int | None]
    sleep_average_respiration_value: NotRequired[float | None]
    sleep_lowest_respiration_value: NotRequired[float | None]
    sleep_highest_respiration_value: NotRequired[float | None]
    sleep_awake_count: NotRequired[int | None]
    sleep_awake_count_qualifier: NotRequired[str | None]
    avg_sleep_stress: NotRequired[float | None]
    sleep_score_feedback: NotRequired[str | None]
    sleep_score_insight: NotRequired[str | None]
    sleep_score_personalized_insight: NotRequired[str | None]
    sleep_overall_score_value: NotRequired[int | None]
    sleep_overall_score_qualifier: NotRequired[str | None]
    sleep_total_duration_qualifier: NotRequired[str | None]
    sleep_stress_qualifier: NotRequired[str | None]
    sleep_rem_percentage_value: NotRequired[int | None]
    sleep_rem_percentage_qualifier: NotRequired[str | None]
    sleep_rem_optimal_start: NotRequired[float | None]
    sleep_rem_optimal_end: NotRequired[float | None]
    sleep_restlessness_qualifier: NotRequired[str | None]
    sleep_restlessness_optimal_start: NotRequired[float | None]
    sleep_restlessness_optimal_end: NotRequired[float | None]
    sleep_light_percentage_value: NotRequired[int | None]
    sleep_light_percentage_qualifier: NotRequired[str | None]
    sleep_light_optimal_start: NotRequired[float | None]
    sleep_light_optimal_end: NotRequired[float | None]
    sleep_deep_percentage_value: NotRequired[int | None]
    sleep_deep_percentage_qualifier: NotRequired[str | None]
    sleep_deep_optimal_start: NotRequired[float | None]
    sleep_deep_optimal_end: NotRequired[float | None]
    sleep_avg_overnight_hrv: NotRequired[float | None]
    sleep_resting_heart_rate: NotRequired[int | None]
    sleep_body_battery_change: NotRequired[int | None]
    sleep_restless_moments_count: NotRequired[int | None]
    sleep_levels_data: NotRequired[list[dict[str, Any]]]
    sleep_heart_rate_data: NotRequired[list[dict[str, Any]]]
    sleep_hrv_data: NotRequired[list[dict[str, Any]]]
    sleep_stress_data: NotRequired[list[dict[str, Any]]]


class UserSummaryRecord(TypedDict, total=False):
    calendar_date: date
    total_kilocalories: NotRequired[float | None]
    active_kilocalories: NotRequired[float | None]
    bmr_kilocalories: NotRequired[float | None]
    total_steps: NotRequired[int | None]
    total_distance_meters: NotRequired[int | None]
    min_heart_rate: NotRequired[int | None]
    max_heart_rate: NotRequired[int | None]
    resting_heart_rate: NotRequired[int | None]
    last_seven_days_avg_resting_heart_rate: NotRequired[int | None]
    vigorous_intensity_minutes: NotRequired[int | None]
    moderate_intensity_minutes: NotRequired[int | None]
    average_stress_level: NotRequired[int | None]
    total_stress_duration: NotRequired[int | None]
    stress_duration: NotRequired[int | None]
    uncategorized_stress_duration: NotRequired[int | None]
    rest_stress_duration: NotRequired[int | None]
    low_stress_duration: NotRequired[int | None]
    activity_stress_duration: NotRequired[int | None]
    medium_stress_duration: NotRequired[int | None]
    high_stress_duration: NotRequired[int | None]
    stress_qualifier: NotRequired[str | None]
    body_battery_charged_value: NotRequired[int | None]
    body_battery_drained_value: NotRequired[int | None]
    body_battery_highest_value: NotRequired[int | None]
    body_battery_lowest_value: NotRequired[int | None]
    body_battery_most_recent_value: NotRequired[int | None]
    avg_waking_respiration_value: NotRequired[float | None]
    highest_respiration_value: NotRequired[float | None]
    lowest_respiration_value: NotRequired[float | None]
    latest_respiration_value: NotRequired[float | None]


class BodyCompositionRecord(TypedDict, total=False):
    calendar_date: date
    weight: NotRequired[float | None]
    bmi: NotRequired[float | None]
    body_fat_mass: NotRequired[float | None]
    body_fat_percentage: NotRequired[float | None]
    body_water_mass: NotRequired[float | None]
    body_water_percentage: NotRequired[float | None]
    bone_mass: NotRequired[float | None]
    bone_mass_percentage: NotRequired[float | None]
    muscle_mass: NotRequired[float | None]
    muscle_mass_percentage: NotRequired[float | None]
    visceral_fat: NotRequired[float | None]
    basal_metabolic_rate: NotRequired[int | None]


class HRVRecord(TypedDict, total=False):
    calendar_date: date
    hrv_weekly_avg: NotRequired[int | None]
    hrv_last_night_avg: NotRequired[int | None]
    hrv_status: NotRequired[str | None]
    hrv_baseline_balanced_low: NotRequired[int | None]
    hrv_baseline_balanced_upper: NotRequired[int | None]


class TrainingReadinessRecord(TypedDict, total=False):
    calendar_date: date
    training_readiness_level: NotRequired[str | None]
    training_readiness_score: NotRequired[int | None]
    sleep_score: NotRequired[int | None]
    sleep_score_factor_feedback: NotRequired[str | None]
    recovery_time_factor_feedback: NotRequired[str | None]
    recovery_time: NotRequired[int | None]
    acute_load: NotRequired[int | None]
    hrv_weekly_average: NotRequired[int | None]
    hrv_factor_feedback: NotRequired[str | None]
    stress_history_factor_feedback: NotRequired[str | None]
    sleep_history_factor_feedback: NotRequired[str | None]


class EnduranceScoreRecord(TypedDict, total=False):
    calendar_date: date
    endurance_score: NotRequired[int | None]
    endurance_score_classification: NotRequired[int | None]
    endurance_score_classification_lower_limit_intermediate: NotRequired[int | None]
    endurance_score_classification_lower_limit_trained: NotRequired[int | None]
    endurance_score_classification_lower_limit_well_trained: NotRequired[int | None]
    endurance_score_classification_lower_limit_expert: NotRequired[int | None]
    endurance_score_classification_lower_limit_superior: NotRequired[int | None]
    endurance_score_classification_lower_limit_elite: NotRequired[int | None]
    endurance_score_contributors: NotRequired[list[dict[str, Any]] | dict[str, Any] | None]


class TrainingStatusRecord(TypedDict, total=False):
    calendar_date: date
    daily_training_load_acute: NotRequired[int | None]
    daily_training_load_acute_feedback: NotRequired[str | None]
    daily_training_load_chronic: NotRequired[float | None]
    min_training_load_chronic: NotRequired[float | None]
    max_training_load_chronic: NotRequired[float | None]
    vo2_max_precise_value: NotRequired[float | None]
    vo2_max_feedback: NotRequired[str | None]
    monthly_load_anaerobic: NotRequired[float | None]
    monthly_load_aerobic_high: NotRequired[float | None]
    monthly_load_aerobic_low: NotRequired[float | None]
    monthly_load_aerobic_low_target_min: NotRequired[float | None]
    monthly_load_aerobic_low_target_max: NotRequired[float | None]
    monthly_load_aerobic_high_target_min: NotRequired[float | None]
    monthly_load_aerobic_high_target_max: NotRequired[float | None]
    monthly_load_anaerobic_target_min: NotRequired[float | None]
    monthly_load_anaerobic_target_max: NotRequired[float | None]
    training_balance_feedback_phrase: NotRequired[str | None]


class FitnessAgeRecord(TypedDict, total=False):
    calendar_date: date
    chronological_age: NotRequired[int | None]
    fitness_age: NotRequired[float | None]
    body_fat_value: NotRequired[float | None]
    vigorous_days_avg_value: NotRequired[float | None]
    rhr_value: NotRequired[int | None]
    vigorous_minutes_avg_value: NotRequired[float | None]


class ActivityRecord(TypedDict, total=False):
    calendar_date: date
    activity_id: int
    activity_type: NotRequired[str | None]
    activity_name: NotRequired[str | None]
    activity_description: NotRequired[str | None]
    activity_start_time: NotRequired[str | None]
    activity_start_latitude: NotRequired[float | None]
    activity_start_longitude: NotRequired[float | None]
    activity_end_latitude: NotRequired[float | None]
    activity_end_longitude: NotRequired[float | None]
    activity_location_name: NotRequired[str | None]
    activity_duration: NotRequired[float | None]
    activity_elapsed_duration: NotRequired[float | None]
    activity_moving_duration: NotRequired[float | None]
    activity_distance: NotRequired[float | None]
    activity_elevation_gain: NotRequired[float | None]
    activity_elevation_loss: NotRequired[float | None]
    activity_min_elevation: NotRequired[float | None]
    activity_max_elevation: NotRequired[float | None]
    activity_calories: NotRequired[float | None]
    activity_bmr_calories: NotRequired[float | None]
    activity_steps: NotRequired[int | None]
    activity_avg_stride_length: NotRequired[float | None]
    activity_average_speed: NotRequired[float | None]
    activity_average_hr: NotRequired[float | None]
    activity_max_hr: NotRequired[float | None]
    activity_watch_min_temperature: NotRequired[float | None]
    activity_watch_max_temperature: NotRequired[float | None]
    activity_weather_temperature_on_start: NotRequired[float | None]
    activity_weather_relative_humidity_on_start: NotRequired[float | None]
    activity_weather_wind_direction_on_start: NotRequired[str | None]
    activity_weather_wind_speed_on_start: NotRequired[float | None]
    activity_weather_wind_gust_on_start: NotRequired[float | None]
    activity_weather_type_desc: NotRequired[str | None]
    activity_water_estimated: NotRequired[float | None]
    activity_aerobic_training_effect: NotRequired[float | None]
    activity_anaerobic_training_effect: NotRequired[float | None]
    activity_activity_training_load: NotRequired[float | None]
    activity_training_effect_label: NotRequired[str | None]
    activity_aerobic_training_effect_message: NotRequired[str | None]
    activity_anaerobic_training_effect_message: NotRequired[str | None]
    activity_moderate_intensity_minutes: NotRequired[int | None]
    activity_vigorous_intensity_minutes: NotRequired[int | None]
    activity_difference_body_battery: NotRequired[int | None]
    activity_secs_in_zone1: NotRequired[float | None]
    activity_secs_in_zone2: NotRequired[float | None]
    activity_secs_in_zone3: NotRequired[float | None]
    activity_secs_in_zone4: NotRequired[float | None]
    activity_secs_in_zone5: NotRequired[float | None]


class ActivityGpsRecord(TypedDict, total=False):
    activity_id: int
    calendar_date: NotRequired[date | None]
    activity_name: NotRequired[str | None]
    gps_data: NotRequired[list[dict[str, Any]] | dict[str, Any] | None]


class DailyHealthEventRecord(TypedDict, total=False):
    calendar_date: date
    last_meal_time: NotRequired[datetime | None]
    last_drink_time: NotRequired[datetime | None]
    last_screen_time: NotRequired[datetime | None]


__all__ = [
    "SleepRecord",
    "UserSummaryRecord",
    "BodyCompositionRecord",
    "HRVRecord",
    "TrainingReadinessRecord",
    "EnduranceScoreRecord",
    "TrainingStatusRecord",
    "FitnessAgeRecord",
    "ActivityRecord",
    "ActivityGpsRecord",
    "DailyHealthEventRecord",
]
