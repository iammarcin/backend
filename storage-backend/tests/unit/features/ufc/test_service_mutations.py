from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core.exceptions import ValidationError
from features.db.ufc.schemas.requests import (
    CreateFighterRequest,
    SubscriptionToggleRequest,
    UpdateFighterRequest,
)
from features.db.ufc.service import UfcService


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _fighter(fighter_id: int) -> SimpleNamespace:
    return SimpleNamespace(id=fighter_id)


@pytest.mark.anyio
async def test_create_fighter_inserts_when_missing() -> None:
    fighters_repo = AsyncMock()
    fighters_repo.create_fighter.return_value = (_fighter(10), True)
    service = UfcService(fighters_repo=fighters_repo)
    session = SimpleNamespace()

    payload = CreateFighterRequest(
        name="Test Fighter",
        ufcUrl="https://example.com/fighters/test",
        fighterFullBodyImgUrl="https://cdn.example.com/test_full.png",
        fighterHeadshotImgUrl="https://cdn.example.com/test_head.png",
        weightClass="lightweight",
        record="10-0-0",
        sherdogRecord="10-0-0",
        tags="[]",
    )

    result = await service.create_fighter(session, payload)

    fighters_repo.create_fighter.assert_awaited_once()
    assert result.status == "created"
    assert result.changed is True
    assert result.fighter_id == 10


@pytest.mark.anyio
async def test_create_fighter_returns_duplicate_status() -> None:
    fighters_repo = AsyncMock()
    fighters_repo.create_fighter.return_value = (_fighter(5), False)
    service = UfcService(fighters_repo=fighters_repo)
    session = SimpleNamespace()

    payload = CreateFighterRequest(
        name="Existing Fighter",
        ufcUrl="https://example.com/fighters/existing",
        fighterFullBodyImgUrl="https://cdn.example.com/existing_full.png",
        fighterHeadshotImgUrl="https://cdn.example.com/existing_head.png",
        weightClass="heavyweight",
        record="12-1-0",
        sherdogRecord="12-1-0",
        tags="[]",
    )

    result = await service.create_fighter(session, payload)

    assert result.status == "duplicate"
    assert result.changed is False
    assert result.fighter_id == 5


@pytest.mark.anyio
async def test_update_fighter_requires_changes() -> None:
    fighters_repo = AsyncMock()
    service = UfcService(fighters_repo=fighters_repo)
    session = SimpleNamespace()

    payload = UpdateFighterRequest()

    with pytest.raises(ValidationError):
        await service.update_fighter(session, fighter_id=1, payload=payload)


@pytest.mark.anyio
async def test_update_fighter_handles_missing_rows() -> None:
    fighters_repo = AsyncMock()
    fighters_repo.update_fighter.return_value = (None, False)
    service = UfcService(fighters_repo=fighters_repo)
    session = SimpleNamespace()

    payload = UpdateFighterRequest(record="11-2-0")

    with pytest.raises(ValidationError) as exc:
        await service.update_fighter(session, fighter_id=99, payload=payload)

    assert exc.value.field == "fighter_id"


@pytest.mark.anyio
async def test_update_fighter_returns_status_flags() -> None:
    fighters_repo = AsyncMock()
    fighters_repo.update_fighter.return_value = (_fighter(4), True)
    service = UfcService(fighters_repo=fighters_repo)
    session = SimpleNamespace()

    payload = UpdateFighterRequest(record="15-0-0")

    result = await service.update_fighter(session, fighter_id=4, payload=payload)

    fighters_repo.update_fighter.assert_awaited_once()
    assert result.status == "updated"
    assert result.changed is True


@pytest.mark.anyio
async def test_toggle_subscription_maps_response() -> None:
    subscriptions_repo = AsyncMock()
    subscriptions_repo.toggle_subscription.return_value = (True, True, None)
    service = UfcService(subscriptions_repo=subscriptions_repo)
    session = SimpleNamespace()

    payload = SubscriptionToggleRequest(person_id=2, fighter_id=3, subscribe=True)

    result = await service.toggle_subscription(session, payload)

    subscriptions_repo.toggle_subscription.assert_awaited_once_with(
        session, person_id=2, fighter_id=3, subscribe=True
    )
    assert result.subscription_status == "1"
    assert result.changed is True
    assert result.person_id == 2
