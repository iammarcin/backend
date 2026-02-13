"""Translators for Garmin activity payloads."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from features.garmin.schemas.queries import GarminDataQuery

from .converters import extract_time_hhmm, extract_zone_seconds
from .gps import resolve_gps_payload
from .utils import (
    coerce_date_key,
    deep_get,
    extract_date,
    iter_mappings,
    parse_datetime,
    query_default_date,
)
from .weather import normalise_weather


def translate_activity(payload: Any, query: GarminDataQuery) -> Iterable[Mapping[str, Any]]:
    """Flatten Garmin activity summaries into ingestion-ready dictionaries."""

    records: list[dict[str, Any]] = []
    for entry in iter_mappings(payload):
        summary = entry.get("summaryDTO") if isinstance(entry.get("summaryDTO"), Mapping) else {}
        weather = entry.get("weatherDTO") if isinstance(entry.get("weatherDTO"), Mapping) else {}

        zone_seconds = extract_zone_seconds(entry)
        weather_metrics = normalise_weather(entry, weather)

        activity_id = entry.get("activityId") or summary.get("activityId") or entry.get("id")
        if activity_id is None:
            continue

        start_time = summary.get("startTimeLocal") or entry.get("startTimeLocal")
        calendar_source = (
            entry.get("calendarDate")
            or summary.get("calendarDate")
            or extract_date(start_time)
            or query_default_date(query)
        )
        calendar_date = coerce_date_key(calendar_source)
        if calendar_date is None:
            continue

        record: dict[str, Any] = {
            "calendar_date": calendar_date,
            "activity_id": activity_id,
            "activity_type": deep_get(entry.get("activityType"), "typeKey") or entry.get("activityType"),
            "activity_name": entry.get("activityName") or summary.get("activityName"),
            "activity_description": entry.get("activityDescription"),
            "activity_location_name": entry.get("locationName") or summary.get("locationName"),
            "activity_start_time": extract_time_hhmm(summary.get("beginTimestamp") or start_time),
            "activity_start_latitude": summary.get("startLatitude")
            or summary.get("startLatitudeDd")
            or entry.get("startLatitude")
            or entry.get("startLatitudeDd"),
            "activity_start_longitude": summary.get("startLongitude")
            or summary.get("startLongitudeDd")
            or entry.get("startLongitude")
            or entry.get("startLongitudeDd"),
            "activity_end_latitude": summary.get("endLatitude")
            or summary.get("endLatitudeDd")
            or entry.get("endLatitude")
            or entry.get("endLatitudeDd"),
            "activity_end_longitude": summary.get("endLongitude")
            or summary.get("endLongitudeDd")
            or entry.get("endLongitude")
            or entry.get("endLongitudeDd"),
            "activity_duration": summary.get("duration") or entry.get("duration"),
            "activity_elapsed_duration": summary.get("elapsedDuration") or entry.get("elapsedDuration"),
            "activity_moving_duration": summary.get("movingDuration") or entry.get("movingDuration"),
            "activity_distance": summary.get("distance") or entry.get("distance"),
            "activity_elevation_gain": summary.get("totalAscent")
            or summary.get("elevationGain")
            or entry.get("totalAscent")
            or entry.get("elevationGain"),
            "activity_elevation_loss": summary.get("totalDescent")
            or summary.get("elevationLoss")
            or entry.get("totalDescent")
            or entry.get("elevationLoss"),
            "activity_min_elevation": summary.get("minElevation") or entry.get("minElevation"),
            "activity_max_elevation": summary.get("maxElevation") or entry.get("maxElevation"),
            "activity_calories": summary.get("calories") or entry.get("calories"),
            "activity_bmr_calories": summary.get("bmrCalories") or entry.get("bmrCalories"),
            "activity_steps": summary.get("steps") or entry.get("steps"),
            "activityAvgStrideLength": summary.get("averageStrideLength")
            or summary.get("avgStrideLength")
            or entry.get("avgStrideLength"),
            "activity_average_speed": summary.get("averageSpeed") or entry.get("averageSpeed"),
            "activity_average_hr": summary.get("averageHR")
            or summary.get("averageHeartRate")
            or entry.get("averageHR")
            or entry.get("averageHeartRate"),
            "activity_max_hr": summary.get("maxHR")
            or summary.get("maxHeartRate")
            or entry.get("maxHR")
            or entry.get("maxHeartRate"),
            "activity_watch_min_temperature": summary.get("minTemperature") or entry.get("minTemperature"),
            "activity_watch_max_temperature": summary.get("maxTemperature") or entry.get("maxTemperature"),
            "activity_weather_temperature_on_start": weather_metrics.get("temperature"),
            "activity_weather_relative_humidity_on_start": weather_metrics.get("humidity"),
            "activity_weather_wind_direction_on_start": weather_metrics.get("wind_direction"),
            "activity_weather_wind_speed_on_start": weather_metrics.get("wind_speed"),
            "activity_weather_wind_gust_on_start": weather_metrics.get("wind_gust"),
            "activity_weather_type_desc": weather_metrics.get("type_desc"),
            "activity_water_estimated": summary.get("waterEstimatedLoss")
            or summary.get("waterEstimated")
            or entry.get("waterEstimatedLoss")
            or entry.get("waterEstimated"),
            "activity_aerobic_training_effect": summary.get("trainingEffect")
            or entry.get("trainingEffect"),
            "activity_anaerobic_training_effect": summary.get("anaerobicTrainingEffect")
            or entry.get("anaerobicTrainingEffect"),
            "activity_activity_training_load": summary.get("activityTrainingLoad")
            or entry.get("activityTrainingLoad"),
            "activity_training_effect_label": summary.get("trainingEffectLabel")
            or entry.get("trainingEffectLabel"),
            "activity_aerobic_training_effect_message": summary.get("aerobicTrainingEffectMessage")
            or entry.get("aerobicTrainingEffectMessage"),
            "activity_anaerobic_training_effect_message": summary.get("anaerobicTrainingEffectMessage")
            or entry.get("anaerobicTrainingEffectMessage"),
            "activity_moderate_intensity_minutes": summary.get("moderateIntensityMinutes")
            or entry.get("moderateIntensityMinutes"),
            "activity_vigorous_intensity_minutes": summary.get("vigorousIntensityMinutes")
            or entry.get("vigorousIntensityMinutes"),
            "activity_difference_body_battery": summary.get("differenceBodyBattery")
            or entry.get("differenceBodyBattery"),
            "activity_secs_in_zone1": summary.get("timeInHrZone1") or zone_seconds.get(1),
            "activity_secs_in_zone2": summary.get("timeInHrZone2") or zone_seconds.get(2),
            "activity_secs_in_zone3": summary.get("timeInHrZone3") or zone_seconds.get(3),
            "activity_secs_in_zone4": summary.get("timeInHrZone4") or zone_seconds.get(4),
            "activity_secs_in_zone5": summary.get("timeInHrZone5") or zone_seconds.get(5),
        }

        records.append({key: value for key, value in record.items() if value is not None})

    return records


def translate_activity_gps(payload: Any, query: GarminDataQuery) -> Iterable[Mapping[str, Any]]:
    """Normalise GPS track payloads for a Garmin activity."""

    records: list[dict[str, Any]] = []
    for entry in iter_mappings(payload):
        activity_id = entry.get("activityId") or query.activity_id
        if activity_id is None:
            continue

        summary = entry.get("summaryDTO") if isinstance(entry.get("summaryDTO"), Mapping) else {}
        calendar_source = (
            entry.get("calendarDate")
            or summary.get("calendarDate")
            or extract_date(summary.get("startTimeLocal"))
            or query_default_date(query)
        )
        calendar_date = coerce_date_key(calendar_source)

        gps_payload = resolve_gps_payload(entry)
        if not gps_payload:
            continue

        activity_name = entry.get("activityName") or summary.get("activityName") or query.activity_name
        if isinstance(activity_name, str):
            activity_name = activity_name.strip() or None

        record: dict[str, Any] = {
            "activity_id": activity_id,
            "calendar_date": calendar_date,
            "activity_name": activity_name,
            "gps_data": gps_payload,
        }

        records.append({key: value for key, value in record.items() if value is not None})

    return records


def translate_daily_health_events(
    payload: Any, query: GarminDataQuery
) -> Iterable[Mapping[str, Any]]:
    """Normalise Garmin daily health event payloads."""

    records: list[dict[str, Any]] = []
    for entry in iter_mappings(payload):
        calendar_source = entry.get("calendarDate") or entry.get("calendar_date") or query_default_date(query)
        calendar_date = coerce_date_key(calendar_source)
        if calendar_date is None:
            continue

        record = {
            "calendar_date": calendar_date,
            "last_meal_time": parse_datetime(entry.get("lastMealTime") or entry.get("last_meal_time")),
            "last_drink_time": parse_datetime(entry.get("lastDrinkTime") or entry.get("last_drink_time")),
            "last_screen_time": parse_datetime(entry.get("lastScreenTime") or entry.get("last_screen_time")),
        }
        records.append({key: value for key, value in record.items() if value is not None})

    return records
