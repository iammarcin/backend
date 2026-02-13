"""OpenAI Batch API operations for text generation."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from config.batch import OPENAI_BATCH_ENDPOINT
from .file_operations import BatchFileOperations
from .job_operations import BatchJobOperations
from .polling_operations import BatchPollingOperations
from .result_operations import BatchResultOperations

logger = logging.getLogger(__name__)


class OpenAIBatchOperations:
    """Encapsulates OpenAI Batch API helpers using composition."""

    def __init__(self, client: AsyncOpenAI) -> None:
        self.client = client
        self.file_ops = BatchFileOperations(client)
        self.job_ops = BatchJobOperations(client)
        self.polling_ops = BatchPollingOperations(client)
        self.result_ops = BatchResultOperations(client)

    async def create_jsonl_file(
        self,
        requests: List[Dict[str, Any]],
        endpoint: str = OPENAI_BATCH_ENDPOINT,
    ) -> Path:
        """Create a JSONL file formatted for OpenAI batch submission."""
        return await self.file_ops.create_jsonl_file(requests, endpoint)

    async def upload_batch_file(self, file_path: Path) -> str:
        """Upload JSONL payload and return file identifier."""
        return await self.file_ops.upload_batch_file(file_path)

    async def create_batch_job(
        self,
        input_file_id: str,
        *,
        description: Optional[str] = None,
        completion_window: str = "24h",
        endpoint: str = OPENAI_BATCH_ENDPOINT,
    ) -> str:
        """Create the batch job and return its identifier."""
        return await self.job_ops.create_batch_job(
            input_file_id,
            description=description,
            completion_window=completion_window,
            endpoint=endpoint,
        )

    async def poll_batch_status(
        self,
        batch_id: str,
        *,
        polling_interval: int = 30,
        timeout: int = 3600,
        status_callback: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Poll batch status until it completes or fails."""
        return await self.polling_ops.poll_batch_status(
            batch_id,
            polling_interval=polling_interval,
            timeout=timeout,
            status_callback=status_callback,
        )

    async def download_results(self, output_file_id: str) -> List[Dict[str, Any]]:
        """Download and parse batch results from OpenAI."""
        return await self.result_ops.download_results(output_file_id)

    async def cleanup_file(self, file_id: Optional[str]) -> None:
        """Delete an uploaded file."""
        await self.file_ops.cleanup_file(file_id)

    async def submit_and_wait(
        self,
        requests: List[Dict[str, Any]],
        *,
        description: Optional[str] = None,
        endpoint: str = OPENAI_BATCH_ENDPOINT,
        status_callback: Optional[Any] = None,
        polling_interval: Optional[int] = None,
        timeout: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Submit a batch job and wait for completion."""

        temp_file = await self.create_jsonl_file(requests, endpoint=endpoint)
        input_file_id: Optional[str] = None
        output_file_id: Optional[str] = None
        results: List[Dict[str, Any]] = []

        try:
            input_file_id = await self.upload_batch_file(temp_file)
            batch_id = await self.create_batch_job(
                input_file_id,
                description=description,
                endpoint=endpoint,
            )
            poll_kwargs = {}
            if polling_interval is not None:
                poll_kwargs["polling_interval"] = polling_interval
            if timeout is not None:
                poll_kwargs["timeout"] = timeout
            batch_result = await self.poll_batch_status(
                batch_id,
                status_callback=status_callback,
                **poll_kwargs,
            )
            output_file_id = batch_result.get("output_file_id")
            results = await self.download_results(output_file_id)

            logger.info(
                "Downloaded batch results",
                extra={
                    "batch_id": batch_id,
                    "result_count": len(results),
                },
            )

            return results
        finally:
            await self.cleanup_file(input_file_id)
            temp_file.unlink(missing_ok=True)


__all__ = ["OpenAIBatchOperations"]
