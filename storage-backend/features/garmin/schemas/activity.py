"""Garmin activity related request models."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

from pydantic import Field, field_validator, model_validator

from .activity_enrichment import apply_weather_metrics, apply_zone_seconds, ensure_calendar_date
from .base import GarminRequest, as_midnight, normalise_iterable, parse_date
from .internal import ActivityGpsRecord, ActivityRecord


class ActivityRequest(GarminRequest):
    """Summary metrics for a recorded Garmin activity."""

    calendar_date: date = Field(alias="calendarDate")
    activity_id: int
    activity_type: str | None = None
    activity_name: str | None = None
    activity_description: str | None = None
    activity_start_time: str | None = None
    activity_start_latitude: float | None = None
    activity_start_longitude: float | None = None
    activity_end_latitude: float | None = None
    activity_end_longitude: float | None = None
    activity_location_name: str | None = None
    activity_duration: float | None = None
    activity_elapsed_duration: float | None = None
    activity_moving_duration: float | None = None
    activity_distance: float | None = None
    activity_elevation_gain: float | None = None
    activity_elevation_loss: float | None = None
    activity_min_elevation: float | None = None
    activity_max_elevation: float | None = None
    activity_calories: float | None = None
    activity_bmr_calories: float | None = None
    activity_steps: int | None = None
    activity_avg_stride_length: float | None = Field(default=None, alias="activityAvgStrideLength")
    activity_average_speed: float | None = None
    activity_average_hr: float | None = None
    activity_max_hr: float | None = None
    activity_watch_min_temperature: float | None = None
    activity_watch_max_temperature: float | None = None
    activity_weather_temperature_on_start: float | None = None
    activity_weather_relative_humidity_on_start: float | None = None
    activity_weather_wind_direction_on_start: str | None = None
    activity_weather_wind_speed_on_start: float | None = None
    activity_weather_wind_gust_on_start: float | None = None
    activity_weather_type_desc: str | None = None
    activity_water_estimated: float | None = None
    activity_aerobic_training_effect: float | None = None
    activity_anaerobic_training_effect: float | None = None
    activity_activity_training_load: float | None = None
    activity_training_effect_label: str | None = None
    activity_aerobic_training_effect_message: str | None = None
    activity_anaerobic_training_effect_message: str | None = None
    activity_moderate_intensity_minutes: int | None = None
    activity_vigorous_intensity_minutes: int | None = None
    activity_difference_body_battery: int | None = None
    activity_secs_in_zone1: float | None = None
    activity_secs_in_zone2: float | None = None
    activity_secs_in_zone3: float | None = None
    activity_secs_in_zone4: float | None = None
    activity_secs_in_zone5: float | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalise_enrichment_fields(cls, value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value

        data = dict(value)

        ensure_calendar_date(data)
        apply_zone_seconds(data)
        apply_weather_metrics(data)

        activity_type_payload = data.get("activityType")
        if isinstance(activity_type_payload, Mapping):
            type_key = activity_type_payload.get("typeKey") or activity_type_payload.get("typeName")
            if isinstance(type_key, str):
                data["activityType"] = type_key

        location_payload = data.get("locationName")
        if isinstance(location_payload, Mapping):
            name = location_payload.get("name")
            if isinstance(name, str):
                data["locationName"] = name

        return data

    _coerce_date = field_validator("calendar_date", mode="before")(parse_date)

    def to_internal(self) -> ActivityRecord:
        """Convert the request payload into the storage DTO."""

        data = self.model_dump(by_alias=False, exclude_none=True)
        data["calendar_date"] = as_midnight(self.calendar_date)
        stride_length = data.pop("activity_avg_stride_length", None)
        if stride_length is not None:
            data["activity_avgStrideLength"] = stride_length
        return ActivityRecord(data)  # type: ignore[arg-type]


class ActivityGpsRequest(GarminRequest):
    """GPS track data associated with a Garmin activity."""

    activity_id: int
    calendar_date: date | None = Field(default=None, alias="calendarDate")
    activity_name: str | None = None
    gps_data: Sequence[Mapping[str, Any]] | Mapping[str, Any] | None = None

    _coerce_date = field_validator("calendar_date", mode="before")(
        lambda value: parse_date(value) if value is not None else value
    )

    def to_internal(self) -> ActivityGpsRecord:
        """Convert the request payload into the storage DTO."""

        data = self.model_dump(by_alias=False, exclude_none=True)
        if "calendar_date" in data and data["calendar_date"] is not None:
            data["calendar_date"] = as_midnight(data["calendar_date"])
        if "gps_data" in data:
            raw = data["gps_data"]
            if isinstance(raw, Mapping):
                data["gps_data"] = dict(raw)
            elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
                data["gps_data"] = normalise_iterable(raw)
        return ActivityGpsRecord(data)  # type: ignore[arg-type]


__all__ = ["ActivityGpsRequest", "ActivityRequest"]
