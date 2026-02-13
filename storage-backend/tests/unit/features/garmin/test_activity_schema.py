from __future__ import annotations

import pytest

from features.garmin.schemas.activity import ActivityRequest


def test_activity_request_derives_enrichment_fields() -> None:
    payload = {
        "activityId": 999,
        "startTimeLocal": "2024-11-05T10:00:00",
        "zones": [
            {"zoneNumber": 1, "secsInZone": "90"},
            {"zoneNumber": 2, "secsInZone": 45.5},
        ],
        "weather_data": {
            "temp": 68,
            "relativeHumidity": "55",
            "windSpeed": 10,
            "windGust": "20",
            "windDirectionCompassPoint": "NW",
            "weatherTypeDTO": {"desc": "clear"},
        },
    }

    request = ActivityRequest.model_validate(payload)

    assert request.calendar_date.isoformat() == "2024-11-05"
    assert request.activity_secs_in_zone1 == pytest.approx(90.0)
    assert request.activity_secs_in_zone2 == pytest.approx(45.5)
    assert request.activity_weather_temperature_on_start == pytest.approx(20.0)
    assert request.activity_weather_relative_humidity_on_start == pytest.approx(55.0)
    assert request.activity_weather_wind_direction_on_start == "NW"
    assert request.activity_weather_wind_speed_on_start == pytest.approx(16.1)
    assert request.activity_weather_wind_gust_on_start == pytest.approx(32.2)
    assert request.activity_weather_type_desc == "clear"


def test_activity_request_preserves_existing_enrichment_values() -> None:
    payload = {
        "calendarDate": "2024-11-05",
        "activityId": 123,
        "activity_secs_in_zone1": 12.0,
        "activity_weather_temperature_on_start": 18.5,
        "zones": [{"zoneNumber": 1, "secsInZone": 30}],
        "weather_data": {"temp": 60},
    }

    request = ActivityRequest.model_validate(payload)

    assert request.activity_secs_in_zone1 == 12.0
    assert request.activity_weather_temperature_on_start == 18.5
