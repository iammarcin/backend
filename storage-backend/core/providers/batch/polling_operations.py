"""Polling operations for batch processing."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from openai import AsyncOpenAI

from config.batch import BATCH_INITIAL_POLLING_DELAY_SECONDS, BATCH_POLLING_INTERVAL_SECONDS, BATCH_TIMEOUT_SECONDS
from core.exceptions import ProviderError
from .batch_result_utils import download_batch_results, process_batch_error_file

logger = logging.getLogger(__name__)


class BatchPollingOperations:
    """Handles polling operations for OpenAI batch processing."""

    def __init__(self, client: AsyncOpenAI) -> None:
        self.client = client

    async def _handle_batch_completed(
        self,
        batch,
        batch_id: str,
        iteration: int,
        elapsed: float,
        request_counts,
    ) -> Dict[str, Any]:
        """Handle completed batch status."""
        output_file_id = batch.output_file_id
        error_file_id = getattr(batch, "error_file_id", None)

        if not output_file_id:
            logger.error(
                "Batch completed but no output_file_id",
                extra={
                    "batch_id": batch_id,
                    "error_file_id": error_file_id,
                    "request_counts": request_counts,
                },
            )

            if error_file_id:
                await process_batch_error_file(self.client, error_file_id, batch_id)

            raise ProviderError(
                (
                    f"Batch {batch_id} completed but no output file available. "
                    f"Succeeded: {getattr(request_counts, 'completed', 0)}, "
                    f"Failed: {getattr(request_counts, 'failed', 0)}"
                ),
                provider="openai",
            )

        logger.info(
            "Batch completed successfully",
            extra={
                "batch_id": batch_id,
                "total_iterations": iteration,
                "total_elapsed_seconds": int(elapsed),
                "request_counts": request_counts,
                "output_file_id": output_file_id,
            },
        )
        return {
            "id": batch.id,
            "status": "completed",
            "output_file_id": output_file_id,
            "error_file_id": error_file_id,
            "request_counts": request_counts,
        }

    async def poll_batch_status(
        self,
        batch_id: str,
        *,
        polling_interval: int = BATCH_POLLING_INTERVAL_SECONDS,
        timeout: int = BATCH_TIMEOUT_SECONDS,
        status_callback: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Poll batch status until it completes or fails."""

        logger.info(
            "Starting batch polling",
            extra={
                "batch_id": batch_id,
                "polling_interval": polling_interval,
                "timeout_seconds": timeout,
            },
        )
        loop = asyncio.get_event_loop()
        start_time = loop.time()
        iteration = 0
        previous_status: Optional[str] = None

        # optional initial delay to allow job propagation
        if BATCH_INITIAL_POLLING_DELAY_SECONDS:
            logger.info(
                "Initial delay before polling",
                extra={
                    "batch_id": batch_id,
                    "delay_seconds": BATCH_INITIAL_POLLING_DELAY_SECONDS,
                },
            )
            await asyncio.sleep(BATCH_INITIAL_POLLING_DELAY_SECONDS)

        while True:
            iteration += 1
            try:
                batch = await self.client.batches.retrieve(batch_id)
            except Exception as exc:  # pragma: no cover - network failure
                logger.exception(
                    "Error retrieving batch status",
                    extra={"batch_id": batch_id, "iteration": iteration},
                )
                raise ProviderError("Batch polling failed", provider="openai") from exc

            status = batch.status
            elapsed = loop.time() - start_time
            request_counts = getattr(batch, "request_counts", None)

            logger.info(
                "Batch polling iteration",
                extra={
                    "batch_id": batch_id,
                    "iteration": iteration,
                    "status": status,
                    "elapsed_seconds": int(elapsed),
                    "request_counts": request_counts,
                },
            )

            if status != previous_status and status_callback:
                await status_callback(status, batch)
                previous_status = status

            if status == "completed":
                return await self._handle_batch_completed(
                    batch, batch_id, iteration, elapsed, request_counts
                )

            if status in {"failed", "cancelled", "expired"}:
                logger.error(
                    "Batch failed",
                    extra={
                        "batch_id": batch_id,
                        "status": status,
                        "elapsed_seconds": int(elapsed),
                    },
                )
                raise ProviderError(f"Batch job {status}", provider="openai")

            if elapsed > timeout:
                logger.error(
                    "Batch polling timeout",
                    extra={
                        "batch_id": batch_id,
                        "timeout_seconds": timeout,
                        "elapsed_seconds": int(elapsed),
                    },
                )
                raise ProviderError(
                    f"Batch polling timeout after {timeout}s",
                    provider="openai",
                )

            logger.debug(
                "Sleeping before next poll",
                extra={
                    "batch_id": batch_id,
                    "sleep_seconds": polling_interval,
                },
            )
            await asyncio.sleep(polling_interval)


__all__ = ["BatchPollingOperations"]