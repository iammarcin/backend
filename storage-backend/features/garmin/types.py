"""Typed dictionary definitions for Garmin repository payloads."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, TypedDict

JsonDict = dict[str, Any]
JsonLike = Any


class GarminSleepPayload(TypedDict, total=False):
    calendar_date: date
    time_offset: str | None
    sleep_time_seconds: int | None
    sleep_start: str | None
    sleep_end: str | None
    sleep_start_gmt: str | None
    sleep_end_gmt: str | None
    nap_time_seconds: int | None
    nap_data: JsonLike
    deep_sleep_seconds: int | None
    light_sleep_seconds: int | None
    rem_sleep_seconds: int | None
    awake_sleep_seconds: int | None
    sleep_average_respiration_value: float | None
    sleep_lowest_respiration_value: float | None
    sleep_highest_respiration_value: float | None
    sleep_awake_count: int | None
    avg_sleep_stress: float | None
    sleep_score_feedback: str | None
    sleep_score_insight: str | None
    sleep_score_personalized_insight: str | None
    sleep_overall_score_value: int | None
    sleep_overall_score_qualifier: str | None
    sleep_total_duration_qualifier: str | None
    sleep_stress_qualifier: str | None
    sleep_awake_count_qualifier: str | None
    sleep_rem_percentage_value: int | None
    sleep_rem_percentage_qualifier: str | None
    sleep_rem_optimal_start: float | None
    sleep_rem_optimal_end: float | None
    sleep_restlessness_qualifier: str | None
    sleep_restlessness_optimal_start: float | None
    sleep_restlessness_optimal_end: float | None
    sleep_light_percentage_value: int | None
    sleep_light_percentage_qualifier: str | None
    sleep_light_optimal_start: float | None
    sleep_light_optimal_end: float | None
    sleep_deep_percentage_value: int | None
    sleep_deep_percentage_qualifier: str | None
    sleep_deep_optimal_start: float | None
    sleep_deep_optimal_end: float | None
    sleep_avg_overnight_hrv: float | None
    sleep_resting_heart_rate: int | None
    sleep_body_battery_change: int | None
    sleep_restless_moments_count: int | None
    sleep_levels_data: JsonLike
    sleep_heart_rate_data: JsonLike
    sleep_hrv_data: JsonLike
    sleep_stress_data: JsonLike


class GarminUserSummaryPayload(TypedDict, total=False):
    calendar_date: date
    total_kilocalories: float | None
    active_kilocalories: float | None
    bmr_kilocalories: float | None
    total_steps: int | None
    total_distance_meters: int | None
    min_heart_rate: int | None
    max_heart_rate: int | None
    resting_heart_rate: int | None
    last_seven_days_avg_resting_heart_rate: int | None
    vigorous_intensity_minutes: int | None
    moderate_intensity_minutes: int | None
    average_stress_level: int | None
    total_stress_duration: int | None
    stress_duration: int | None
    uncategorized_stress_duration: int | None
    rest_stress_duration: int | None
    low_stress_duration: int | None
    activity_stress_duration: int | None
    medium_stress_duration: int | None
    high_stress_duration: int | None
    stress_qualifier: str | None
    body_battery_charged_value: int | None
    body_battery_drained_value: int | None
    body_battery_highest_value: int | None
    body_battery_lowest_value: int | None
    body_battery_most_recent_value: int | None
    avg_waking_respiration_value: float | None
    highest_respiration_value: float | None
    lowest_respiration_value: float | None
    latest_respiration_value: float | None


class GarminBodyCompositionPayload(TypedDict, total=False):
    calendar_date: date
    weight: float | None
    bmi: float | None
    body_fat_mass: float | None
    body_fat_percentage: float | None
    body_water_mass: float | None
    body_water_percentage: float | None
    bone_mass: float | None
    bone_mass_percentage: float | None
    muscle_mass: float | None
    muscle_mass_percentage: float | None
    visceral_fat: float | None
    basal_metabolic_rate: int | None


class GarminHRVPayload(TypedDict, total=False):
    calendar_date: date
    hrv_weekly_avg: int | None
    hrv_last_night_avg: int | None
    hrv_status: str | None
    hrv_baseline_balanced_low: int | None
    hrv_baseline_balanced_upper: int | None


class GarminTrainingReadinessPayload(TypedDict, total=False):
    calendar_date: date
    training_readiness_level: str | None
    training_readiness_score: int | None
    sleep_score: int | None
    sleep_score_factor_feedback: str | None
    recovery_time_factor_feedback: str | None
    recovery_time: int | None
    acute_load: int | None
    hrv_weekly_average: int | None
    hrv_factor_feedback: str | None
    stress_history_factor_feedback: str | None
    sleep_history_factor_feedback: str | None


class GarminEnduranceScorePayload(TypedDict, total=False):
    calendar_date: date
    endurance_score: int | None
    endurance_score_classification: int | None
    endurance_score_classification_lower_limit_intermediate: int | None
    endurance_score_classification_lower_limit_trained: int | None
    endurance_score_classification_lower_limit_well_trained: int | None
    endurance_score_classification_lower_limit_expert: int | None
    endurance_score_classification_lower_limit_superior: int | None
    endurance_score_classification_lower_limit_elite: int | None
    endurance_score_contributors: JsonLike


class GarminTrainingStatusPayload(TypedDict, total=False):
    calendar_date: date
    daily_training_load_acute: int | None
    daily_training_load_acute_feedback: str | None
    daily_training_load_chronic: float | None
    min_training_load_chronic: float | None
    max_training_load_chronic: float | None
    vo2_max_precise_value: float | None
    vo2_max_feedback: str | None
    monthly_load_anaerobic: float | None
    monthly_load_aerobic_high: float | None
    monthly_load_aerobic_low: float | None
    monthly_load_aerobic_low_target_min: float | None
    monthly_load_aerobic_low_target_max: float | None
    monthly_load_aerobic_high_target_min: float | None
    monthly_load_aerobic_high_target_max: float | None
    monthly_load_anaerobic_target_min: float | None
    monthly_load_anaerobic_target_max: float | None
    training_balance_feedback_phrase: str | None


class GarminFitnessAgePayload(TypedDict, total=False):
    calendar_date: date
    chronological_age: int | None
    fitness_age: float | None
    body_fat_value: float | None
    vigorous_days_avg_value: float | None
    rhr_value: int | None
    vigorous_minutes_avg_value: float | None


class GarminActivityPayload(TypedDict, total=False):
    calendar_date: date
    activity_id: int
    activity_type: str | None
    activity_name: str | None
    activity_description: str | None
    activity_start_time: str | None
    activity_start_latitude: float | None
    activity_start_longitude: float | None
    activity_end_latitude: float | None
    activity_end_longitude: float | None
    activity_location_name: str | None
    activity_duration: float | None
    activity_elapsed_duration: float | None
    activity_moving_duration: float | None
    activity_distance: float | None
    activity_elevation_gain: float | None
    activity_elevation_loss: float | None
    activity_min_elevation: float | None
    activity_max_elevation: float | None
    activity_calories: float | None
    activity_bmr_calories: float | None
    activity_steps: int | None
    activity_avgStrideLength: float | None
    activity_average_speed: float | None
    activity_average_hr: float | None
    activity_max_hr: float | None
    activity_watch_min_temperature: float | None
    activity_watch_max_temperature: float | None
    activity_weather_temperature_on_start: float | None
    activity_weather_relative_humidity_on_start: float | None
    activity_weather_wind_direction_on_start: str | None
    activity_weather_wind_speed_on_start: float | None
    activity_weather_wind_gust_on_start: float | None
    activity_weather_type_desc: str | None
    activity_water_estimated: float | None
    activity_aerobic_training_effect: float | None
    activity_anaerobic_training_effect: float | None
    activity_activity_training_load: float | None
    activity_training_effect_label: str | None
    activity_aerobic_training_effect_message: str | None
    activity_anaerobic_training_effect_message: str | None
    activity_moderate_intensity_minutes: int | None
    activity_vigorous_intensity_minutes: int | None
    activity_difference_body_battery: int | None
    activity_secs_in_zone1: float | None
    activity_secs_in_zone2: float | None
    activity_secs_in_zone3: float | None
    activity_secs_in_zone4: float | None
    activity_secs_in_zone5: float | None


class GarminActivityGpsPayload(TypedDict, total=False):
    activity_id: str
    calendar_date: date | None
    activity_name: str | None
    gps_data: JsonLike


class GarminDailyHealthEventsPayload(TypedDict, total=False):
    calendar_date: date
    last_meal_time: datetime | None
    last_drink_time: datetime | None
    last_screen_time: datetime | None


__all__ = [
    "GarminSleepPayload",
    "GarminUserSummaryPayload",
    "GarminBodyCompositionPayload",
    "GarminHRVPayload",
    "GarminTrainingReadinessPayload",
    "GarminEnduranceScorePayload",
    "GarminTrainingStatusPayload",
    "GarminFitnessAgePayload",
    "GarminActivityPayload",
    "GarminActivityGpsPayload",
    "GarminDailyHealthEventsPayload",
    "JsonDict",
    "JsonLike",
]
