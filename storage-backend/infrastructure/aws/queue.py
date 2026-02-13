"""Helpers for interacting with Amazon SQS."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping

from botocore.exceptions import BotoCoreError, ClientError

from config.aws import AWS_SQS_QUEUE_URL
from core.exceptions import ConfigurationError, ServiceError

from .clients import get_sqs_client

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class QueueMessageMetadata:
    """Metadata returned after enqueuing a message."""

    queue_url: str
    message_id: str | None = None


class SqsQueueService:
    """Send domain payloads to an SQS queue."""

    def __init__(
        self,
        *,
        queue_url: str | None = None,
        sqs_client: Any | None = None,
    ) -> None:
        client = sqs_client or get_sqs_client()
        if client is None:
            raise ConfigurationError("SQS client not initialised", key="AWS credentials")

        resolved_queue_url = queue_url or AWS_SQS_QUEUE_URL
        if not resolved_queue_url:
            raise ConfigurationError(
                "AWS_SQS_QUEUE_URL must be configured",
                key="AWS_SQS_QUEUE_URL",
            )

        self._queue_url = resolved_queue_url
        self._sqs_client = client

    async def enqueue(
        self,
        payload: Mapping[str, Any],
        *,
        message_group_id: str | None = None,
        message_deduplication_id: str | None = None,
        delay_seconds: int | None = None,
    ) -> QueueMessageMetadata:
        """Serialise ``payload`` to JSON and send it to the queue."""

        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        params: dict[str, Any] = {
            "QueueUrl": self._queue_url,
            "MessageBody": body,
        }
        if message_group_id:
            params["MessageGroupId"] = message_group_id
        if message_deduplication_id:
            params["MessageDeduplicationId"] = message_deduplication_id
        if delay_seconds is not None:
            params["DelaySeconds"] = delay_seconds

        logger.info("Enqueuing payload to SQS", extra={"queue_url": self._queue_url})

        try:
            response = await asyncio.to_thread(self._sqs_client.send_message, **params)
        except (BotoCoreError, ClientError) as exc:
            logger.exception("Failed to enqueue payload to SQS", extra={"queue_url": self._queue_url})
            raise ServiceError("Failed to enqueue message to SQS") from exc

        message_id = None
        if isinstance(response, Mapping):
            message_id = response.get("MessageId")  # type: ignore[assignment]

        logger.debug(
            "Payload enqueued to SQS", extra={"queue_url": self._queue_url, "message_id": message_id}
        )
        return QueueMessageMetadata(queue_url=self._queue_url, message_id=message_id)

    async def enqueue_timestamped_payload(
        self,
        payload: Mapping[str, Any],
        *,
        message_group_id: str | None = None,
        message_deduplication_id: str | None = None,
        delay_seconds: int | None = None,
    ) -> QueueMessageMetadata:
        """Enqueue ``payload`` with an added ``created_at`` timestamp."""

        extended = dict(payload)
        extended.setdefault("created_at", datetime.now(UTC).isoformat(timespec="seconds"))
        return await self.enqueue(
            extended,
            message_group_id=message_group_id,
            message_deduplication_id=message_deduplication_id,
            delay_seconds=delay_seconds,
        )


__all__ = ["QueueMessageMetadata", "SqsQueueService"]
