from __future__ import annotations

from datetime import UTC, datetime

import pytest


pytestmark = pytest.mark.requires_docker

from features.db.ufc.db_models import Fighter, Person
from features.db.ufc.repositories.fighters import FighterReadRepository
from features.db.ufc.repositories.subscriptions import SubscriptionReadRepository


@pytest.mark.asyncio
async def test_create_fighter_is_idempotent(session):
    repo = FighterReadRepository()
    fighter_data = {
        "name": "Integration Fighter",
        "ufc_url": "https://example.com/fighters/integration",
        "fighter_full_body_img_url": "https://cdn.example.com/integration_full.png",
        "fighter_headshot_img_url": "https://cdn.example.com/integration_head.png",
        "weight_class": "welterweight",
        "record": "8-0-0",
        "sherdog_record": "8-0-0",
        "tags": "[]",
    }

    fighter, created = await repo.create_fighter(session, fighter_data)
    assert created is True

    duplicate, created_again = await repo.create_fighter(session, fighter_data)
    assert created_again is False
    assert duplicate.id == fighter.id


@pytest.mark.asyncio
async def test_update_fighter_changes_and_noops(session):
    repo = FighterReadRepository()
    fighter = Fighter(
        name="Mutable Fighter",
        ufc_url="https://example.com/fighters/mutable",
        fighter_full_body_img_url="https://cdn.example.com/mutable_full.png",
        fighter_headshot_img_url="https://cdn.example.com/mutable_head.png",
        weight_class="middleweight",
        record="5-0-0",
        sherdog_record="5-0-0",
        tags="[]",
    )
    session.add(fighter)
    await session.flush()

    updates = {"record": "6-0-0", "instagram": "https://instagram.com/mutable"}
    updated, changed = await repo.update_fighter(session, fighter_id=fighter.id, updates=updates)
    assert updated is not None
    assert changed is True
    assert updated.record == "6-0-0"

    _, changed_again = await repo.update_fighter(session, fighter_id=fighter.id, updates=updates)
    assert changed_again is False


@pytest.mark.asyncio
async def test_toggle_subscription_is_idempotent(session):
    fighters_repo = FighterReadRepository()
    subscriptions_repo = SubscriptionReadRepository()

    fighter_data = {
        "name": "Subscribed Fighter",
        "ufc_url": "https://example.com/fighters/subscribed",
        "fighter_full_body_img_url": "https://cdn.example.com/sub_full.png",
        "fighter_headshot_img_url": "https://cdn.example.com/sub_head.png",
        "weight_class": "featherweight",
        "record": "9-1-0",
        "sherdog_record": "9-1-0",
        "tags": "[]",
    }

    fighter, _ = await fighters_repo.create_fighter(session, fighter_data)
    person = Person(
        account_name="subscriber",
        email="subscriber@example.com",
        password="hashed",
        created_at=datetime.now(UTC),
    )
    session.add(person)
    await session.flush()

    status, changed, timestamp = await subscriptions_repo.toggle_subscription(
        session, person_id=person.id, fighter_id=fighter.id, subscribe=True
    )
    assert status is True
    assert changed is True
    assert timestamp is not None

    status_again, changed_again, _ = await subscriptions_repo.toggle_subscription(
        session, person_id=person.id, fighter_id=fighter.id, subscribe=True
    )
    assert status_again is True
    assert changed_again is False

    status_unsub, changed_unsub, _ = await subscriptions_repo.toggle_subscription(
        session, person_id=person.id, fighter_id=fighter.id, subscribe=False
    )
    assert status_unsub is False
    assert changed_unsub is True

    status_unsub_again, changed_unsub_again, _ = await subscriptions_repo.toggle_subscription(
        session, person_id=person.id, fighter_id=fighter.id, subscribe=False
    )
    assert status_unsub_again is False
    assert changed_unsub_again is False
