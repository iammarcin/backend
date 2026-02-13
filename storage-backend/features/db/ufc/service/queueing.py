"""Queue dispatch helpers for UFC fighter ingestion."""

from __future__ import annotations

import logging

from core.exceptions import ConfigurationError, ValidationError
from infrastructure.aws.queue import QueueMessageMetadata, SqsQueueService
from ..schemas import FighterQueueRequest, FighterQueueResult

logger = logging.getLogger(__name__)


class FighterQueueCoordinator:
    """Handle interactions with the AWS SQS queue for fighter candidates."""

    def __init__(self, queue_service: SqsQueueService | None) -> None:
        self._queue_service = queue_service

    async def enqueue_candidate(self, payload: FighterQueueRequest) -> FighterQueueResult:
        """Send a fighter candidate payload to the configured SQS queue."""

        if self._queue_service is None:
            raise ConfigurationError(
                "SQS queue service is not configured",
                key="AWS_SQS_QUEUE_URL",
            )

        name = payload.full_name.strip()
        if not name:
            raise ValidationError("full_name is required", field="full_name")

        description = (payload.description or "").strip()
        dwcs_info = (payload.dwcs_info or "").strip() or None

        message_payload = {
            "customer_id": payload.customer_id,
            "fighter": {
                "full_name": name,
            },
        }
        if description:
            message_payload["fighter"]["description"] = description
        if dwcs_info:
            message_payload["fighter"]["dwcs_info"] = dwcs_info

        logger.info(
            "Queueing fighter candidate",
            extra={"full_name": name, "customer_id": payload.customer_id},
        )

        metadata: QueueMessageMetadata = await self._queue_service.enqueue_timestamped_payload(
            message_payload
        )

        logger.info(
            "Fighter candidate enqueued",
            extra={"queue_url": metadata.queue_url, "message_id": metadata.message_id},
        )

        return FighterQueueResult(
            status="queued",
            message="Fighter candidate enqueued",
            queue_url=metadata.queue_url,
            message_id=metadata.message_id,
        )


__all__ = ["FighterQueueCoordinator"]
