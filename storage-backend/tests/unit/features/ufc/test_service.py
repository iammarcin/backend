from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core.exceptions import ConfigurationError, ServiceError, ValidationError
from features.db.ufc.schemas import (
    FighterListParams,
    FighterSearchParams,
    FighterSubscriptionParams,
    FighterQueueRequest,
)
from features.db.ufc.service import UfcService
from infrastructure.aws.queue import QueueMessageMetadata


@pytest.fixture
def anyio_backend() -> str:
    """Ensure pytest-anyio uses asyncio."""

    return "asyncio"


def _fighter_row(fighter_id: int, name: str, *, subscribed: bool | None = None) -> dict[str, str | int]:
    row: dict[str, str | int] = {
        "id": fighter_id,
        "name": name,
        "ufcUrl": "https://example.com",  # minimal required fields
        "fighterFullBodyImgUrl": "https://example.com/full.png",
        "fighterHeadshotImgUrl": "https://example.com/head.png",
        "weightClass": "Lightweight",
        "record": "10-0-0",
        "sherdogRecord": "5-0-0",
        "tags": "striker",
    }
    if subscribed is not None:
        row["subscription_status"] = "1" if subscribed else "0"
    return row


class StubQueueService:
    def __init__(
        self,
        *,
        metadata: QueueMessageMetadata | None = None,
        error: Exception | None = None,
    ) -> None:
        self.metadata = metadata or QueueMessageMetadata(
            queue_url="https://example.com/queue", message_id="msg-123"
        )
        self.error = error
        self.calls: list[dict[str, object]] = []

    async def enqueue_timestamped_payload(self, payload: dict[str, object]) -> QueueMessageMetadata:
        self.calls.append(payload)
        if self.error:
            raise self.error
        return self.metadata


@pytest.mark.anyio
async def test_list_fighters_paginates_results() -> None:
    fighters_repo = AsyncMock()
    fighters_repo.list_fighters.return_value = [
        _fighter_row(1, "Fighter One"),
        _fighter_row(2, "Fighter Two"),
        _fighter_row(3, "Fighter Three"),
    ]
    service = UfcService(fighters_repo=fighters_repo)
    session = SimpleNamespace()

    params = FighterListParams(page=2, page_size=1)
    result = await service.list_fighters(session, params)

    fighters_repo.list_fighters.assert_awaited_once_with(session)
    assert result.total == 3
    assert result.page == 2
    assert result.page_size == 1
    assert result.has_more is True
    assert [item.id for item in result.items] == [2]


@pytest.mark.anyio
async def test_list_fighters_with_subscriptions_passes_filters() -> None:
    fighters_repo = AsyncMock()
    fighters_repo.list_fighters_with_subscriptions.return_value = [
        _fighter_row(1, "Amanda", subscribed=True),
        _fighter_row(2, "Beatriz", subscribed=False),
    ]
    service = UfcService(fighters_repo=fighters_repo)
    session = SimpleNamespace()

    params = FighterSubscriptionParams(page_size=2, user_id=42, search="  Amanda  ")
    result = await service.list_fighters_with_subscriptions(session, params)

    fighters_repo.list_fighters_with_subscriptions.assert_awaited_once_with(
        session, user_id=42, search="Amanda"
    )
    assert result.subscriptions_enabled is True
    assert [item.subscription_status for item in result.items] == ["1", "0"]


@pytest.mark.anyio
async def test_search_fighters_requires_search_term() -> None:
    fighters_repo = AsyncMock()
    service = UfcService(fighters_repo=fighters_repo)
    session = SimpleNamespace()

    with pytest.raises(ValueError):
        FighterSearchParams(page_size=10, search="   ")

    params = FighterSearchParams(page_size=10, search="Gaethje")
    fighters_repo.search_fighters.return_value = [_fighter_row(1, "Justin Gaethje")]

    result = await service.search_fighters(session, params)

    fighters_repo.search_fighters.assert_awaited_once_with(session, search="Gaethje")
    assert result.items[0].name == "Justin Gaethje"


@pytest.mark.anyio
async def test_find_fighter_by_id_returns_none_when_missing() -> None:
    fighters_repo = AsyncMock()
    fighters_repo.list_fighters.return_value = [_fighter_row(1, "Valentina")]
    service = UfcService(fighters_repo=fighters_repo)
    session = SimpleNamespace()

    result = await service.find_fighter_by_id(session, 99)

    assert result is None
    fighters_repo.list_fighters.assert_awaited_once_with(session)


@pytest.mark.anyio
async def test_list_subscription_summaries_returns_typed_payload() -> None:
    subscriptions_repo = AsyncMock()
    subscriptions_repo.list_subscription_summaries.return_value = [
        {
            "accountName": "Jane",
            "email": "jane@example.com",
            "subscriptions": ["1", "2"],
        }
    ]
    service = UfcService(subscriptions_repo=subscriptions_repo)
    session = SimpleNamespace()

    result = await service.list_subscription_summaries(session)

    subscriptions_repo.list_subscription_summaries.assert_awaited_once_with(session)
    assert result.total == 1
    assert result.items[0].accountName == "Jane"


@pytest.mark.anyio
async def test_page_size_validation() -> None:
    service = UfcService(max_page_size=5)
    session = SimpleNamespace()

    params = FighterListParams(page_size=10)
    with pytest.raises(ValidationError):
        await service.list_fighters(session, params)


@pytest.mark.anyio
async def test_page_bounds_validation() -> None:
    fighters_repo = AsyncMock()
    fighters_repo.list_fighters.return_value = [_fighter_row(1, "Fighter One")]
    service = UfcService(fighters_repo=fighters_repo)
    session = SimpleNamespace()

    params = FighterListParams(page=2, page_size=1)
    with pytest.raises(ValidationError):
        await service.list_fighters(session, params)


@pytest.mark.anyio
async def test_enqueue_fighter_candidate_sends_payload() -> None:
    queue_service = StubQueueService()
    service = UfcService(queue_service=queue_service)

    payload = FighterQueueRequest(
        full_name="Jane Doe",
        description="  Rising prospect  ",
        dwcs_info="  contender  ",
        customer_id=7,
    )

    result = await service.enqueue_fighter_candidate(payload)

    assert queue_service.calls, "Queue service should be invoked"
    message = queue_service.calls[0]
    assert message["customer_id"] == 7
    assert message["fighter"]["full_name"] == "Jane Doe"
    assert message["fighter"]["description"] == "Rising prospect"
    assert message["fighter"]["dwcs_info"] == "contender"
    assert result.status == "queued"
    assert result.queue_url == queue_service.metadata.queue_url


@pytest.mark.anyio
async def test_enqueue_fighter_candidate_requires_queue_service() -> None:
    service = UfcService()
    payload = FighterQueueRequest(full_name="Queued Fighter")

    with pytest.raises(ConfigurationError):
        await service.enqueue_fighter_candidate(payload)


@pytest.mark.anyio
async def test_enqueue_fighter_candidate_propagates_service_error() -> None:
    queue_service = StubQueueService(error=ServiceError("boom"))
    service = UfcService(queue_service=queue_service)
    payload = FighterQueueRequest(full_name="Errored Fighter")

    with pytest.raises(ServiceError):
        await service.enqueue_fighter_candidate(payload)
