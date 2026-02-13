"""Payload enrichment helpers for activity request validation."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from .activity_converters import coerce_float, fahrenheit_to_celsius, mph_to_kph


def iter_zone_entries(source: Any) -> Iterable[Mapping[str, Any]]:
    """Yield zone entry mappings from various payload formats."""
    if isinstance(source, Mapping):
        yield source
    elif isinstance(source, Sequence) and not isinstance(source, (str, bytes)):
        for item in source:
            if isinstance(item, Mapping):
                yield item


def apply_zone_seconds(data: dict[str, Any]) -> None:
    """Populate ``activity_secs_in_zone*`` fields from raw zone payloads.

    Modifies data dict in-place.
    """
    zone_sources: list[Any] = []
    for key in ("zones", "hr_zones", "hrTimeInZones", "timeInZones"):
        payload = data.get(key)
        if payload:
            zone_sources.append(payload)

    summary_dto = data.get("summaryDTO")
    if isinstance(summary_dto, Mapping):
        summary_zones = summary_dto.get("zones") or summary_dto.get("hrZones")
        if summary_zones:
            zone_sources.append(summary_zones)

    if not zone_sources:
        return

    extracted: dict[int, float] = {}
    for source in zone_sources:
        for entry in iter_zone_entries(source):
            number = entry.get("zoneNumber") or entry.get("number") or entry.get("zone")
            seconds = (
                entry.get("secsInZone")
                or entry.get("timeInZone")
                or entry.get("secs")
                or entry.get("seconds")
            )
            try:
                zone_index = int(number)
            except (TypeError, ValueError):
                continue

            if not 1 <= zone_index <= 5:
                continue

            duration = coerce_float(seconds)
            if duration is None:
                continue
            extracted.setdefault(zone_index, duration)

    for zone_index, duration in extracted.items():
        key = f"activity_secs_in_zone{zone_index}"
        if data.get(key) is None:
            data[key] = duration


def apply_weather_metrics(data: dict[str, Any]) -> None:
    """Populate weather-related activity fields from common payload shapes.

    Modifies data dict in-place.
    """
    weather_sources: list[Mapping[str, Any]] = []
    for key in ("weather_data", "weather", "weatherDTO"):
        payload = data.get(key)
        if isinstance(payload, Mapping):
            weather_sources.append(payload)

    summary_dto = data.get("summaryDTO")
    if isinstance(summary_dto, Mapping):
        summary_weather = summary_dto.get("weather") or summary_dto.get("weatherDTO")
        if isinstance(summary_weather, Mapping):
            weather_sources.append(summary_weather)

    if not weather_sources:
        return

    merged: dict[str, Any] = {}
    for payload in weather_sources:
        merged.update(payload)

    if data.get("activity_weather_temperature_on_start") is None:
        temperature = merged.get("temperature")
        temp_c = coerce_float(temperature)
        if temp_c is None and merged.get("temp") is not None:
            temp_c = fahrenheit_to_celsius(merged.get("temp"))
        if temp_c is not None:
            data["activity_weather_temperature_on_start"] = temp_c

    if data.get("activity_weather_relative_humidity_on_start") is None:
        humidity = merged.get("relativeHumidity") or merged.get("humidity")
        humidity_value = coerce_float(humidity)
        if humidity_value is not None:
            data["activity_weather_relative_humidity_on_start"] = humidity_value

    if data.get("activity_weather_wind_direction_on_start") is None:
        wind_direction = merged.get("windDirectionCompassPoint") or merged.get("windDirection")
        if isinstance(wind_direction, str) and wind_direction:
            data["activity_weather_wind_direction_on_start"] = wind_direction

    if data.get("activity_weather_wind_speed_on_start") is None:
        wind_speed = merged.get("windSpeed") or merged.get("windSpeedMph") or merged.get("windSpeedMps")
        speed_value = mph_to_kph(wind_speed) if wind_speed is not None else None
        if speed_value is not None:
            data["activity_weather_wind_speed_on_start"] = speed_value

    if data.get("activity_weather_wind_gust_on_start") is None:
        wind_gust = merged.get("windGust") or merged.get("windGustMph") or merged.get("windGustMps")
        gust_value = mph_to_kph(wind_gust) if wind_gust is not None else None
        if gust_value is not None:
            data["activity_weather_wind_gust_on_start"] = gust_value

    if data.get("activity_weather_type_desc") is None:
        weather_type = None
        weather_type_dto = merged.get("weatherTypeDTO")
        if isinstance(weather_type_dto, Mapping):
            weather_type = weather_type_dto.get("desc") or weather_type_dto.get("displayName")
        if weather_type is None:
            weather_type = merged.get("condition") or merged.get("conditionDesc")
        if isinstance(weather_type, str) and weather_type:
            data["activity_weather_type_desc"] = weather_type


def ensure_calendar_date(data: dict[str, Any]) -> None:
    """Fallback calendar date derivation for payloads lacking ``calendarDate``.

    Modifies data dict in-place.
    """
    if data.get("calendarDate") or data.get("calendar_date"):
        return

    start_time = data.get("startTimeLocal")
    if isinstance(start_time, str) and start_time:
        data["calendarDate"] = start_time.split("T", 1)[0].split(" ", 1)[0]
        return

    summary_dto = data.get("summaryDTO")
    if isinstance(summary_dto, Mapping):
        calendar_date = summary_dto.get("calendarDate")
        if isinstance(calendar_date, str) and calendar_date:
            data["calendarDate"] = calendar_date
