import json
from typing import Any

import pytest
from botocore.exceptions import ClientError

from core.exceptions import ConfigurationError, ServiceError
from infrastructure.aws.queue import QueueMessageMetadata, SqsQueueService


class DummySqsClient:
    def __init__(self, response: dict[str, Any] | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._response = response or {"MessageId": "123"}

    def send_message(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return self._response


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    """Ensure tests run on the asyncio backend."""

    return "asyncio"


async def test_enqueue_timestamped_payload_adds_created_at(monkeypatch):
    monkeypatch.delenv("AWS_SQS_QUEUE_URL", raising=False)
    service = SqsQueueService(queue_url="https://example.com/queue", sqs_client=DummySqsClient())

    payload = {"fighter": {"full_name": "Tester"}}
    metadata = await service.enqueue_timestamped_payload(payload)

    assert isinstance(metadata, QueueMessageMetadata)
    assert metadata.queue_url == "https://example.com/queue"
    assert metadata.message_id == "123"

    assert len(service._sqs_client.calls) == 1  # type: ignore[attr-defined]
    sent = service._sqs_client.calls[0]  # type: ignore[attr-defined]
    assert sent["QueueUrl"] == "https://example.com/queue"

    body = json.loads(sent["MessageBody"])
    assert body["fighter"]["full_name"] == "Tester"
    assert "created_at" in body


async def test_enqueue_raises_service_error_on_failure(monkeypatch):
    class FailingClient(DummySqsClient):
        def send_message(self, **kwargs: Any) -> dict[str, Any]:  # pragma: no cover - exercised via ServiceError path
            raise ClientError({"Error": {"Code": "Boom", "Message": "fail"}}, "SendMessage")

    monkeypatch.delenv("AWS_SQS_QUEUE_URL", raising=False)
    service = SqsQueueService(queue_url="https://example.com/queue", sqs_client=FailingClient())

    with pytest.raises(ServiceError):
        await service.enqueue({"foo": "bar"})


def test_initialisation_requires_queue_url(monkeypatch):
    monkeypatch.delenv("AWS_SQS_QUEUE_URL", raising=False)
    monkeypatch.setattr("core.config.AWS_SQS_QUEUE_URL", "", raising=False)
    monkeypatch.setattr("infrastructure.aws.queue.AWS_SQS_QUEUE_URL", "", raising=False)

    with pytest.raises(ConfigurationError):
        SqsQueueService(sqs_client=DummySqsClient(), queue_url=None)


