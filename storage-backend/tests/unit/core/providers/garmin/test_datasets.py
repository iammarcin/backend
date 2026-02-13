"""Unit tests for Garmin dataset client helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

from core.providers.garmin.datasets import GarminDatasetMixin


class MockClient(GarminDatasetMixin):
    """Minimal concrete client with injectable request handler for testing."""

    def __init__(self):
        self._request = MagicMock()


def test_fetch_activity_weather():
    """It should request the weather endpoint for the given activity."""

    client = MockClient()
    client._request.return_value = {
        "temp": 22,
        "apparentTemp": 20,
        "weatherTypeDTO": {"weatherType": "cloudy"},
    }

    result = client.fetch_activity_weather(12345678)

    client._request.assert_called_once_with(
        "/activity-service/activity/12345678/weather"
    )
    assert result["temp"] == 22
    assert result["weatherTypeDTO"]["weatherType"] == "cloudy"


def test_fetch_activity_hr_zones():
    """It should request the heart-rate zones endpoint for the given activity."""

    client = MockClient()
    client._request.return_value = {
        "zone0Low": 0,
        "zone0High": 120,
        "zone0InSeconds": 600,
        "zone1InSeconds": 1200,
    }

    result = client.fetch_activity_hr_zones(12345678)

    client._request.assert_called_once_with(
        "/activity-service/activity/12345678/hrTimeInZones"
    )
    assert result["zone0InSeconds"] == 600
    assert result["zone1InSeconds"] == 1200


def test_fetch_activity_weather_not_found():
    """It should return ``None`` when weather data is unavailable."""

    client = MockClient()
    client._request.return_value = None

    result = client.fetch_activity_weather(12345678)

    assert result is None
