"""Anthropic Message Batches API helper operations."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List

from anthropic import AsyncAnthropic

from config.batch.defaults import (
    BATCH_POLLING_INTERVAL_SECONDS,
    BATCH_TIMEOUT_SECONDS,
)
from core.exceptions import ProviderError

import logging

logger = logging.getLogger(__name__)


class AnthropicBatchOperations:
    """Encapsulates Anthropic Message Batches API workflows."""

    def __init__(self, client: AsyncAnthropic) -> None:
        self.client = client

    async def submit_inline_batch(self, requests: List[Dict[str, Any]]) -> str:
        """Submit a batch job using inline request payloads."""

        logger.info("Submitting Anthropic inline batch with %d requests", len(requests))
        try:
            batch = await self.client.messages.batches.create(requests=requests)
        except Exception as exc:  # pragma: no cover - network failure
            logger.exception("Failed to submit Anthropic batch")
            raise ProviderError("Anthropic batch submission failed", provider="anthropic", original_error=exc) from exc

        logger.info("Created Anthropic batch %s", batch.id)
        return batch.id

    async def submit_file_batch(self, file_path: Path) -> str:
        """Submit a batch job from JSONL file payload."""

        logger.info("Loading Anthropic batch file %s", file_path)
        requests: List[Dict[str, Any]] = []
        with file_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                payload = line.strip()
                if not payload:
                    continue
                requests.append(json.loads(payload))

        return await self.submit_inline_batch(requests)

    async def poll_batch_status(
        self,
        batch_id: str,
        *,
        polling_interval: int = BATCH_POLLING_INTERVAL_SECONDS,
        timeout: int = BATCH_TIMEOUT_SECONDS,
    ) -> Dict[str, Any]:
        """Poll the batch job until it reaches a terminal state."""

        logger.info("Polling Anthropic batch %s", batch_id)
        loop = asyncio.get_running_loop()
        start_time = loop.time()

        while True:
            try:
                batch = await self.client.messages.batches.retrieve(batch_id)
            except Exception as exc:  # pragma: no cover - network failure
                logger.exception("Failed to retrieve Anthropic batch status")
                raise ProviderError("Anthropic batch polling failed", provider="anthropic", original_error=exc) from exc

            status = getattr(batch, "processing_status", None)
            if status == "ended":
                counts = getattr(batch, "request_counts", None)
                logger.info("Anthropic batch %s completed", batch_id)
                return {
                    "id": batch.id,
                    "processing_status": status,
                    "request_counts": {
                        "processing": getattr(counts, "processing", 0) if counts else 0,
                        "succeeded": getattr(counts, "succeeded", 0) if counts else 0,
                        "errored": getattr(counts, "errored", 0) if counts else 0,
                        "canceled": getattr(counts, "canceled", 0) if counts else 0,
                        "expired": getattr(counts, "expired", 0) if counts else 0,
                    },
                    "results_url": getattr(batch, "results_url", None),
                }

            elapsed = loop.time() - start_time
            if elapsed > timeout:
                raise ProviderError(f"Batch {batch_id} polling timeout after {timeout}s", provider="anthropic")

            await asyncio.sleep(polling_interval)

    async def download_results(self, batch_id: str) -> List[Dict[str, Any]]:
        """Download Anthropic batch results."""

        logger.info("Downloading results for Anthropic batch %s", batch_id)
        results: List[Dict[str, Any]] = []
        try:
            # results() is a coroutine that returns an async iterator
            result_iterator = await self.client.messages.batches.results(batch_id)
            async for result in result_iterator:
                custom_id = getattr(result, "custom_id", None)
                result_data = getattr(result, "result", None)

                results.append(
                    {
                        "custom_id": custom_id,
                        "result": result_data,
                    }
                )

                logger.debug(
                    "Processed Anthropic batch result",
                    extra={
                        "batch_id": batch_id,
                        "custom_id": custom_id,
                        "has_error": bool(getattr(result_data, "error", None)) if result_data else False,
                    },
                )
        except Exception as exc:  # pragma: no cover - network failure
            logger.exception("Failed to download Anthropic batch results")
            raise ProviderError("Failed to download Anthropic batch results", provider="anthropic", original_error=exc) from exc

        logger.info("Downloaded %d Anthropic batch results", len(results))
        if not results:
            logger.warning("Anthropic batch %s returned no results", batch_id)
        return results

    async def cancel_batch(self, batch_id: str) -> None:
        """Cancel an in-flight batch job."""

        logger.info("Cancelling Anthropic batch %s", batch_id)
        try:
            await self.client.messages.batches.cancel(batch_id)
        except Exception as exc:  # pragma: no cover - network failure
            logger.exception("Failed to cancel Anthropic batch")
            raise ProviderError("Failed to cancel Anthropic batch", provider="anthropic", original_error=exc) from exc

    async def submit_and_wait(self, requests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Submit a batch job and return the completed results."""

        batch_id = await self.submit_inline_batch(requests)
        await self.poll_batch_status(batch_id)
        return await self.download_results(batch_id)


__all__ = ["AnthropicBatchOperations"]
