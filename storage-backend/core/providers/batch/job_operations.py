"""Job operations for batch processing."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from openai import AsyncOpenAI

from config.batch import OPENAI_BATCH_COMPLETION_WINDOW, OPENAI_BATCH_ENDPOINT
from core.exceptions import ProviderError

logger = logging.getLogger(__name__)


class BatchJobOperations:
    """Handles job operations for OpenAI batch processing."""

    def __init__(self, client: AsyncOpenAI) -> None:
        self.client = client

    async def create_batch_job(
        self,
        input_file_id: str,
        *,
        description: Optional[str] = None,
        completion_window: str = OPENAI_BATCH_COMPLETION_WINDOW,
        endpoint: str = OPENAI_BATCH_ENDPOINT,
    ) -> str:
        """Create the batch job and return its identifier."""

        metadata = {}
        if description:
            metadata["description"] = description

        try:
            batch = await self.client.batches.create(
                input_file_id=input_file_id,
                endpoint=endpoint,
                completion_window=completion_window,
                metadata=metadata,
            )
        except Exception as exc:  # pragma: no cover - network failure
            logger.exception("Failed to create batch job")
            raise ProviderError(f"Batch job creation failed: {exc}", provider="openai") from exc

        logger.info(
            "Batch job created",
            extra={
                "batch_id": batch.id,
                "input_file_id": input_file_id,
                "endpoint": endpoint,
                "completion_window": completion_window,
            },
        )
        return batch.id


__all__ = ["BatchJobOperations"]