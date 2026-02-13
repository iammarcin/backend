"""Integration tests for Garmin repositories using a transient MySQL database."""

from __future__ import annotations

from datetime import datetime

import pytest


pytestmark = pytest.mark.requires_docker

from features.db.garmin.db_models import (
    ActivityData,
    DailyHealthEvents,
    SleepData,
    TrainingStatus,
)
from features.db.garmin.repositories.activity import GarminActivityRepository
from features.db.garmin.repositories.sleep import GarminSleepRepository
from features.db.garmin.repositories.training import GarminTrainingRepository


@pytest.mark.asyncio
async def test_upsert_sleep_insert_and_update(session):
    repo = GarminSleepRepository()
    payload = {
        "calendar_date": datetime(2024, 6, 1, 0, 0, 0),
        "sleep_time_seconds": 100,
        "sleep_start": "22:00",
        "sleep_end": "06:00",
    }

    record = await repo.upsert_sleep(session, payload, customer_id=1)
    assert record.id is not None
    assert record.sleep_time_seconds == 100

    payload_update = dict(payload)
    payload_update["sleep_time_seconds"] = 200

    updated = await repo.upsert_sleep(session, payload_update, customer_id=1)
    assert updated.id == record.id
    assert updated.sleep_time_seconds == 200

    fetched = await session.get(SleepData, record.id)
    assert fetched is not None
    assert fetched.sleep_time_seconds == 200


@pytest.mark.asyncio
async def test_upsert_training_status_deduplicates(session):
    repo = GarminTrainingRepository()
    payload = {
        "calendar_date": datetime(2024, 6, 2, 0, 0, 0),
        "daily_training_load_acute": 50,
    }

    record = await repo.upsert_training_status(session, payload, customer_id=2)
    assert record.daily_training_load_acute == 50

    payload_update = dict(payload)
    payload_update["daily_training_load_acute"] = 75

    updated = await repo.upsert_training_status(session, payload_update, customer_id=2)
    assert updated.id == record.id
    assert updated.daily_training_load_acute == 75

    fetched = await session.get(TrainingStatus, record.id)
    assert fetched is not None
    assert fetched.daily_training_load_acute == 75


@pytest.mark.asyncio
async def test_upsert_activity_and_daily_health(session):
    repo = GarminActivityRepository()
    activity_payload = {
        "calendar_date": datetime(2024, 6, 3, 0, 0, 0),
        "activity_id": 999,
        "activity_name": "Morning Run",
        "activity_distance": 5.5,
    }

    activity = await repo.upsert_activity(session, activity_payload, customer_id=3)
    assert activity.activity_distance == 5.5

    activity_update = dict(activity_payload)
    activity_update["activity_distance"] = 7.0

    activity_updated = await repo.upsert_activity(session, activity_update, customer_id=3)
    assert activity_updated.id == activity.id
    assert activity_updated.activity_distance == 7.0

    fetched_activity = await session.get(ActivityData, activity.id)
    assert fetched_activity is not None
    assert fetched_activity.activity_distance == 7.0

    health_payload = {
        "calendar_date": datetime(2024, 6, 3, 0, 0, 0),
        "last_meal_time": datetime(2024, 6, 2, 20, 0, 0),
    }

    health = await repo.upsert_daily_health_event(session, health_payload, customer_id=3)
    assert health.last_meal_time.hour == 20

    health_update = dict(health_payload)
    health_update["last_screen_time"] = datetime(2024, 6, 2, 22, 0, 0)

    health_updated = await repo.upsert_daily_health_event(session, health_update, customer_id=3)
    assert health_updated.id == health.id
    assert health_updated.last_screen_time.hour == 22

    fetched_health = await session.get(DailyHealthEvents, health.id)
    assert fetched_health is not None
    assert fetched_health.last_screen_time.hour == 22
