from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import asyncio
from typing import Awaitable, TypeVar

import pytest

from core.exceptions import ConfigurationError, ProviderError
from features.db.garmin.service import GarminService
from features.garmin.schemas.queries import GarminDataQuery
from features.garmin.service import GarminProviderService


T = TypeVar("T")


def run(coro: Awaitable[T]) -> T:
    """Execute ``coro`` in an isolated event loop."""

    return asyncio.run(coro)


class StubClient:
    def __init__(self) -> None:
        self._metadata = {
            "display_name": "tester",
            "full_name": "Test User",
            "unit_system": "metric",
            "session_path": "/tmp/garmin_session.json",
            "domain": "connect.garmin.com",
        }

    @property
    def display_name(self) -> str:  # pragma: no cover - trivial property
        return "tester"

    def metadata(self) -> dict[str, object]:  # pragma: no cover - defensive
        return dict(self._metadata)

    def status(self) -> dict[str, object]:  # pragma: no cover - fallback
        return dict(self._metadata)

    def fetch_sleep(self, *, display_name: str, start: date, end: date | None = None):
        return [
            {
                "calendarDate": start.isoformat(),
                "dailySleepDTO": {
                    "sleepTimeSeconds": 25200,
                    "sleepStartTimestampGMT": 0,
                    "sleepStartTimestampLocal": 0,
                    "sleepEndTimestampGMT": 0,
                    "sleepEndTimestampLocal": 0,
                    "avgSleepStress": 10,
                },
                "dailyNapDTOS": [],
                "sleepLevels": [],
                "sleepHeartRate": [],
                "hrvData": [],
                "sleepStress": [],
            }
        ]

    def fetch_user_summary(self, *, display_name: str, start: date, end: date | None = None):
        return [
            {
                "calendarDate": start.isoformat(),
                "totalSteps": 5000,
            }
        ]

    def fetch_body_composition(self, *, start: date, end: date | None = None):
        return {
            "dateWeightList": [
                {
                    "calendarDate": (end or start).isoformat(),
                    "weight": 78.5,
                    "bmi": 23.2,
                }
            ]
        }


class WithingsStub:
    def metadata(self) -> dict[str, object]:  # pragma: no cover - trivial metadata
        return {
            "token_path": "/tmp/withings.json",
            "has_access_token": True,
            "has_refresh_token": True,
            "scope": "user.metrics",
        }

    def fetch_body_composition(
        self,
        *,
        start: date,
        end: date | None = None,
        height_cm: float | None = None,
    ) -> list[dict[str, object]]:
        return [
            {
                "calendar_date": start,
                "visceral_fat": 9.1,
                "basal_metabolic_rate": 1525,
                "body_fat_percentage": 18.2,
            }
        ]


class WithingsFailingStub(WithingsStub):
    def fetch_body_composition(self, *, start: date, end: date | None = None, height_cm: float | None = None):
        raise ProviderError("withings down", provider="withings")


def test_fetch_dataset_without_persistence_returns_serialised_rows():
    client = StubClient()
    garmin_service = GarminService(
        sleep_repo=MagicMock(),
        summary_repo=MagicMock(),
        training_repo=MagicMock(),
        activity_repo=MagicMock(),
    )
    provider = GarminProviderService(client=client, garmin_service=garmin_service, save_to_db_default=False)

    query = GarminDataQuery(start_date=date(2024, 7, 1))
    result = run(provider.fetch_dataset("sleep", query, customer_id=1, save_to_db=False, session=None))

    assert result.saved is False
    assert result.items[0]["sleep_time_seconds"] == 25200
    assert result.raw[0]["dailySleepDTO"]["sleepTimeSeconds"] == 25200


def test_fetch_dataset_requires_session_when_saving():
    client = StubClient()
    garmin_service = GarminService(
        sleep_repo=MagicMock(),
        summary_repo=MagicMock(),
        training_repo=MagicMock(),
        activity_repo=MagicMock(),
    )
    provider = GarminProviderService(client=client, garmin_service=garmin_service, save_to_db_default=True)

    query = GarminDataQuery(start_date=date(2024, 7, 1))

    with pytest.raises(ConfigurationError):
        run(provider.fetch_dataset("summary", query, customer_id=1, save_to_db=True, session=None))


def test_body_composition_merges_withings_payloads():
    client = StubClient()
    garmin_service = GarminService(
        sleep_repo=MagicMock(),
        summary_repo=MagicMock(),
        training_repo=MagicMock(),
        activity_repo=MagicMock(),
    )
    provider = GarminProviderService(
        client=client,
        garmin_service=garmin_service,
        save_to_db_default=False,
        withings_client=WithingsStub(),
    )

    query = GarminDataQuery(start_date=date(2024, 7, 1))
    result = run(provider.fetch_dataset("body_composition", query, customer_id=5, save_to_db=False, session=None))

    assert result.saved is False
    assert result.items[0]["weight"] == pytest.approx(78.5)
    assert result.items[0]["visceral_fat"] == pytest.approx(9.1)
    assert result.items[0]["basal_metabolic_rate"] == 1525


def test_body_composition_returns_garmin_when_withings_missing():
    client = StubClient()
    garmin_service = GarminService(
        sleep_repo=MagicMock(),
        summary_repo=MagicMock(),
        training_repo=MagicMock(),
        activity_repo=MagicMock(),
    )
    provider = GarminProviderService(client=client, garmin_service=garmin_service, save_to_db_default=False)

    query = GarminDataQuery(start_date=date(2024, 7, 1))
    result = run(provider.fetch_dataset("body_composition", query, customer_id=5, save_to_db=False, session=None))

    assert result.saved is False
    assert result.items[0]["weight"] == pytest.approx(78.5)
    assert "visceral_fat" not in result.items[0]


def test_body_composition_handles_withings_failure():
    client = StubClient()
    garmin_service = GarminService(
        sleep_repo=MagicMock(),
        summary_repo=MagicMock(),
        training_repo=MagicMock(),
        activity_repo=MagicMock(),
    )
    provider = GarminProviderService(
        client=client,
        garmin_service=garmin_service,
        save_to_db_default=False,
        withings_client=WithingsFailingStub(),
    )

    query = GarminDataQuery(start_date=date(2024, 7, 1))
    result = run(provider.fetch_dataset("body_composition", query, customer_id=5, save_to_db=False, session=None))

    assert result.items[0]["weight"] == pytest.approx(78.5)
