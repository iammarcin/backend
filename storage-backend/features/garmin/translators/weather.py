"""Weather data normalization for Garmin activities."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .converters import fahrenheit_to_celsius, mph_to_kph


def normalise_weather(entry: Mapping[str, Any], summary_weather: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize weather data from various Garmin payload formats.

    Merges weather data from multiple sources and normalizes units:
    - Temperature: converted from Fahrenheit to Celsius if needed
    - Wind speed/gust: converted from mph to kph if needed
    - Humidity: extracted from various field names
    - Wind direction: extracted from various field names
    - Weather type: extracted from nested DTO or direct fields

    Args:
        entry: Activity entry that may contain weather data
        summary_weather: Weather data from summary DTO

    Returns:
        Dictionary with normalized weather metrics
    """
    candidates: list[Mapping[str, Any]] = []
    for key in ("weather", "weather_data", "weatherDTO"):
        value = entry.get(key)
        if isinstance(value, Mapping):
            candidates.append(value)

    if isinstance(summary_weather, Mapping):
        candidates.append(summary_weather)

    merged: dict[str, Any] = {}
    for candidate in candidates:
        merged.update(candidate)

    if not merged:
        return {}

    # Temperature normalization
    temp_c: float | None = None
    if merged.get("temperature") is not None:
        try:
            temp_c = float(merged.get("temperature"))
        except (TypeError, ValueError):
            temp_c = None
    if temp_c is None and merged.get("temp") is not None:
        temp_c = fahrenheit_to_celsius(merged.get("temp"))

    # Extract other weather metrics with fallbacks
    humidity = merged.get("relativeHumidity") or merged.get("humidity")
    wind_direction = merged.get("windDirectionCompassPoint") or merged.get("windDirection")
    wind_speed = merged.get("windSpeed") or merged.get("windSpeedMph")
    wind_gust = merged.get("windGust") or merged.get("windGustMph")

    # Weather type extraction
    weather_type = None
    weather_type_dto = merged.get("weatherTypeDTO")
    if isinstance(weather_type_dto, Mapping):
        weather_type = weather_type_dto.get("desc") or weather_type_dto.get("displayName")
    if weather_type is None:
        weather_type = merged.get("condition") or merged.get("conditionDesc")

    return {
        "temperature": temp_c,
        "humidity": humidity,
        "wind_direction": wind_direction,
        "wind_speed": mph_to_kph(wind_speed) if wind_speed is not None else None,
        "wind_gust": mph_to_kph(wind_gust) if wind_gust is not None else None,
        "type_desc": weather_type,
    }
