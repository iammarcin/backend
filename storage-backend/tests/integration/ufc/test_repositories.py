"""Integration tests for UFC repositories."""

from __future__ import annotations

from datetime import datetime

import pytest


pytestmark = pytest.mark.requires_docker

from features.db.ufc.db_models import Fighter, Person, Subscription
from features.db.ufc.repositories.fighters import FighterReadRepository
from features.db.ufc.repositories.subscriptions import SubscriptionReadRepository


@pytest.fixture()
async def ufc_seed(session):
    """Populate the UFC schema with fighters, people, and subscriptions."""

    fighter_a = Fighter(
        name="Fighter A",
        ufc_url="https://example.com/fighters/a",
        fighter_full_body_img_url="https://cdn.example.com/a_full.png",
        fighter_headshot_img_url="https://cdn.example.com/a_head.png",
        weight_class="lightweight",
        record="10-0-0",
        sherdog_record="10-0-0",
        next_fight_date=datetime(2024, 7, 1, 12, 0, 0),
        next_fight_opponent="Fighter B",
        next_fight_opponent_record="8-2-0",
        opponent_headshot_url="https://cdn.example.com/b_head.png",
        opponent_ufc_url="https://example.com/fighters/b",
        tags='["striker"]',
        tags_dwcs="DWCS",
        height="70",
        weight="155",
        age=30,
        rumour_next_fight_date=datetime(2024, 8, 1, 12, 0, 0),
        rumour_next_fight_opponent="Fighter C",
        rumour_next_fight_opponent_record="9-1-0",
        rumour_next_fight_opponent_img_url="https://cdn.example.com/c_head.png",
        rumour_opponent_ufc_url="https://example.com/fighters/c",
        description="Champion",
        twitter="https://twitter.com/fighter_a",
        instagram="https://instagram.com/fighter_a",
        sherdog="https://sherdog.com/fighter_a",
    )

    fighter_b = Fighter(
        name="Fighter B",
        ufc_url="https://example.com/fighters/b",
        fighter_full_body_img_url="https://cdn.example.com/b_full.png",
        fighter_headshot_img_url="https://cdn.example.com/b_head.png",
        weight_class="welterweight",
        record="12-3-0",
        sherdog_record="12-3-0",
        tags='["grappler"]',
        tags_dwcs="DWCS",
        height="72",
        weight="170",
        age=28,
        description="Submission specialist",
        twitter="https://twitter.com/fighter_b",
        instagram="https://instagram.com/fighter_b",
        sherdog="https://sherdog.com/fighter_b",
    )

    fighter_c = Fighter(
        name="Fighter C",
        ufc_url="https://example.com/fighters/c",
        fighter_full_body_img_url="https://cdn.example.com/c_full.png",
        fighter_headshot_img_url="https://cdn.example.com/c_head.png",
        weight_class="middleweight",
        record="5-1-0",
        sherdog_record="5-1-0",
        tags="[]",
        height=None,
        weight="185",
        age=26,
    )

    person_a = Person(
        account_name="Subscriber",
        email="subscriber@example.com",
        password="hashed",
    )
    person_b = Person(
        account_name="Observer",
        email="observer@example.com",
        password="hashed",
    )

    session.add_all([fighter_a, fighter_b, fighter_c, person_a, person_b])
    await session.flush()

    subscription = Subscription(person_id=person_a.id, fighter_id=fighter_a.id)
    session.add(subscription)
    await session.flush()

    return {
        "fighters": [fighter_a, fighter_b, fighter_c],
        "people": [person_a, person_b],
    }


@pytest.mark.asyncio
async def test_list_fighters_returns_all_rows(session, ufc_seed):
    repo = FighterReadRepository()

    rows = await repo.list_fighters(session)
    assert [row["name"] for row in rows] == ["Fighter A", "Fighter B", "Fighter C"]
    assert rows[0]["nextFightDate"] == "2024-07-01T12:00:00"
    assert rows[0]["rumourNextFightDate"] == "2024-08-01T12:00:00"


@pytest.mark.asyncio
async def test_list_fighters_with_subscriptions_filters_and_marks(session, ufc_seed):
    repo = FighterReadRepository()
    subscriber_id = ufc_seed["people"][0].id

    rows = await repo.list_fighters_with_subscriptions(
        session, user_id=subscriber_id
    )

    # Fighter C is missing height, so only two fighters remain
    assert [row["name"] for row in rows] == ["Fighter A", "Fighter B"]
    assert rows[0]["subscription_status"] == "1"
    assert rows[1]["subscription_status"] == "0"

    # Search should narrow down to fighter A by tag
    filtered = await repo.list_fighters_with_subscriptions(
        session, user_id=subscriber_id, search="Striker"
    )
    assert [row["name"] for row in filtered] == ["Fighter A"]


@pytest.mark.asyncio
async def test_search_fighters_matches_partial_values(session, ufc_seed):
    repo = FighterReadRepository()

    rows = await repo.search_fighters(session, search="grappler")
    assert [row["name"] for row in rows] == ["Fighter B"]


@pytest.mark.asyncio
async def test_list_subscription_summaries_returns_grouped_ids(session, ufc_seed):
    repo = SubscriptionReadRepository()

    summaries = await repo.list_subscription_summaries(session)
    assert len(summaries) == 2

    subscriber = next(summary for summary in summaries if summary["email"] == "subscriber@example.com")
    observer = next(summary for summary in summaries if summary["email"] == "observer@example.com")

    assert subscriber["subscriptions"] == [str(ufc_seed["fighters"][0].id)]
    assert observer["subscriptions"] == []
