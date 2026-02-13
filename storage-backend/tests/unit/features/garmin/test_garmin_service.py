"""Unit tests for the Garmin service layer."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.exceptions import ValidationError
from features.garmin.results import IngestResult
from features.garmin.schemas.queries import GarminDataQuery
from features.garmin.schemas.requests import (
    ActivityGpsRequest,
    SleepIngestRequest,
    TrainingReadinessRequest,
)
from features.db.garmin.service import GarminService


@pytest.fixture
def anyio_backend() -> str:
    """Limit tests to the asyncio backend to avoid requiring trio."""

    return "asyncio"


@pytest.mark.anyio
async def test_ingest_sleep_normalises_payload():
    sleep_repo = AsyncMock()
    sleep_repo.upsert_sleep.return_value = SimpleNamespace(calendar_date=datetime(2024, 6, 1))
    service = GarminService(
        sleep_repo=sleep_repo,
        summary_repo=MagicMock(),
        training_repo=MagicMock(),
        activity_repo=MagicMock(),
    )

    payload = SleepIngestRequest.model_validate(
        {
            "calendarDate": "2024-06-01",
            "dailySleepDTO": {
                "sleepTimeSeconds": 25200,
                "sleepStartTimestampGMT": 1717200000000,
                "sleepStartTimestampLocal": 1717207200000,
                "sleepEndTimestampGMT": 1717228800000,
                "sleepEndTimestampLocal": 1717236000000,
                "napTimeSeconds": 1200,
                "deepSleepSeconds": 5400,
                "lightSleepSeconds": 10800,
                "remSleepSeconds": 5040,
                "awakeSleepSeconds": 3600,
                "avgSleepStress": 12.5,
            },
            "dailyNapDTOS": [
                {
                    "napTimeSec": 1200,
                    "napFeedback": "restorative",
                    "napStartTimestampGMT": "2024-06-01T12:00:00Z",
                    "napEndTimestampGMT": "2024-06-01T12:20:00Z",
                }
            ],
            "sleepLevels": [
                {"startGMT": "2024-06-01T00:00:00Z", "endGMT": "2024-06-01T00:30:00Z", "activityLevel": 1}
            ],
            "sleepHeartRate": [
                {"startGMT": 1717200000000, "value": 54},
                {"startGMT": 1717200300000, "value": 56},
            ],
            "hrvData": [{"startGMT": 1717200000000, "value": 65}],
            "sleepStress": [{"startGMT": 1717200000000, "value": 18}],
        }
    )

    result = await service.ingest_sleep(MagicMock(), payload, customer_id=7)

    sleep_repo.upsert_sleep.assert_awaited_once()
    _, args, _ = sleep_repo.upsert_sleep.mock_calls[0]
    internal_payload = args[1]
    assert internal_payload["calendar_date"] == datetime(2024, 6, 1).date()
    assert internal_payload["sleep_time_seconds"] == 25200
    assert internal_payload["nap_data"] and len(internal_payload["nap_data"]) == 1
    assert isinstance(result, IngestResult)
    assert result.metadata["nap_segments"] == 1


@pytest.mark.anyio
async def test_ingest_activity_gps_tracks_points():
    activity_repo = AsyncMock()
    activity_repo.upsert_activity_gps.return_value = SimpleNamespace(calendar_date=None)
    service = GarminService(
        sleep_repo=MagicMock(),
        summary_repo=MagicMock(),
        training_repo=MagicMock(),
        activity_repo=activity_repo,
    )

    payload = ActivityGpsRequest.model_validate(
        {
            "activityId": 42,
            "calendarDate": "2024-06-02",
            "gpsData": [
                {"lat": 51.1, "lng": -1.1},
                {"lat": 51.2, "lng": -1.2},
            ],
        }
    )

    result = await service.ingest_activity_gps(MagicMock(), payload, customer_id=3)

    activity_repo.upsert_activity_gps.assert_awaited_once()
    internal = activity_repo.upsert_activity_gps.await_args.args[1]
    assert isinstance(internal["gps_data"], list)
    assert result.metadata["points"] == 2


@pytest.mark.anyio
async def test_with_session_uses_session_scope(monkeypatch):
    service = GarminService(
        sleep_repo=MagicMock(),
        summary_repo=MagicMock(),
        training_repo=MagicMock(),
        activity_repo=MagicMock(),
    )

    calls: list[Any] = []

    @asynccontextmanager
    async def fake_scope(factory):
        calls.append(factory)
        yield "session"

    monkeypatch.setattr("features.db.garmin.service.session_scope", fake_scope)

    handler = AsyncMock(return_value="ok")
    factory = object()

    result = await service.with_session(factory, handler)

    assert calls == [factory]
    handler.assert_awaited_once_with("session")
    assert result == "ok"


@pytest.mark.anyio
async def test_validate_wraps_errors():
    service = GarminService(
        sleep_repo=MagicMock(),
        summary_repo=MagicMock(),
        training_repo=MagicMock(),
        activity_repo=MagicMock(),
    )

    with pytest.raises(ValidationError):
        service.validate(TrainingReadinessRequest, {"calendarDate": "invalid"})


@pytest.mark.anyio
async def test_fetch_dataset_serialises_records():
    sleep_repo = MagicMock()
    sleep_repo.fetch_sleep = AsyncMock(
        return_value=[
            SimpleNamespace(
                calendar_date=datetime(2024, 6, 1), sleep_time_seconds=25200
            )
        ]
    )

    service = GarminService(
        sleep_repo=sleep_repo,
        summary_repo=MagicMock(),
        training_repo=MagicMock(),
        activity_repo=MagicMock(),
    )

    result = await service.fetch_dataset(MagicMock(), "sleep", GarminDataQuery(), customer_id=4)

    sleep_repo.fetch_sleep.assert_awaited_once()
    assert result[0]["calendar_date"].startswith("2024-06-01")
    assert result[0]["sleep_time_seconds"] == 25200


@pytest.mark.anyio
async def test_fetch_analysis_returns_optimized_bundle():
    def _row():
        return SimpleNamespace(calendar_date=datetime(2024, 6, 1))

    sleep_repo = MagicMock()
    sleep_repo.fetch_sleep = AsyncMock(return_value=[_row()])

    summary_repo = MagicMock()
    summary_repo.fetch_user_summary = AsyncMock(return_value=[_row()])
    summary_repo.fetch_body_composition = AsyncMock(return_value=[_row()])
    summary_repo.fetch_hrv = AsyncMock(return_value=[_row()])

    training_repo = MagicMock()
    training_repo.fetch_training_readiness = AsyncMock(return_value=[_row()])
    training_repo.fetch_endurance_score = AsyncMock(return_value=[_row()])
    training_repo.fetch_training_status = AsyncMock(return_value=[_row()])
    training_repo.fetch_fitness_age = AsyncMock(return_value=[_row()])

    activity_repo = MagicMock()
    activity_repo.fetch_activity = AsyncMock(return_value=[_row()])
    activity_repo.fetch_activity_gps = AsyncMock(return_value=[_row()])
    activity_repo.fetch_daily_health_events = AsyncMock(return_value=[_row()])

    service = GarminService(
        sleep_repo=sleep_repo,
        summary_repo=summary_repo,
        training_repo=training_repo,
        activity_repo=activity_repo,
    )

    payload = await service.fetch_analysis(
        MagicMock(),
        GarminDataQuery(),
        customer_id=1,
        include_optimized=True,
    )

    assert "datasets" in payload
    assert payload["datasets"]["get_sleep_data"][0]["calendar_date"].startswith("2024-06-01")
    assert isinstance(payload["optimized"], list)
