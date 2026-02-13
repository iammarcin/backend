"""Remote job helpers for OpenAI Batch API requests."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Iterable

from openai import AsyncOpenAI

from core.exceptions import ProviderError

logger = logging.getLogger(__name__)


async def upload_batch_file(client: AsyncOpenAI, file_path: Path) -> str:
    """Upload JSONL file to OpenAI and return file identifier."""

    try:
        with file_path.open("rb") as handle:
            response = await client.files.create(file=handle, purpose="batch")
    except Exception as exc:  # pragma: no cover - network failure
        logger.error("Failed to upload batch file", exc_info=True)
        raise ProviderError(f"Batch file upload failed: {exc}") from exc

    file_id = response.id
    logger.info("Uploaded batch file", extra={"file_id": file_id})
    return file_id


async def create_remote_batch_job(
    client: AsyncOpenAI,
    input_file_id: str,
    *,
    description: str = "Semantic search embedding batch",
) -> str:
    """Create the Batch API job and return its identifier."""

    try:
        response = await client.batches.create(
            input_file_id=input_file_id,
            endpoint="/v1/embeddings",
            completion_window="24h",
            metadata={"description": description},
        )
    except Exception as exc:  # pragma: no cover - network failure
        logger.error("Failed to create batch job", exc_info=True)
        raise ProviderError(f"Batch job creation failed: {exc}") from exc

    batch_id = response.id
    logger.info(
        "Created batch job",
        extra={"batch_id": batch_id, "status": response.status},
    )
    return batch_id


async def wait_for_batch_completion(
    client: AsyncOpenAI,
    batch_id: str,
    *,
    poll_interval: int = 10,
    timeout: int = 7200,
) -> dict[str, Any]:
    """Poll Batch API status until it finishes or fails."""

    loop = asyncio.get_event_loop()
    start_time = loop.time()

    while True:
        try:
            batch = await client.batches.retrieve(batch_id)
        except Exception as exc:  # pragma: no cover - network failure
            logger.error("Error polling batch status", exc_info=True)
            raise ProviderError(f"Batch polling failed: {exc}") from exc

        status = batch.status
        logger.debug(
            "Batch status update",
            extra={"batch_id": batch_id, "status": status},
        )

        if status == "completed":
            logger.info("Batch completed", extra={"batch_id": batch_id})
            return {
                "status": "completed",
                "output_file_id": batch.output_file_id,
                "request_counts": getattr(batch, "request_counts", None),
            }

        if status in {"failed", "cancelled", "expired"}:
            error_info = getattr(batch, "errors", None)
            logger.error(
                "Batch failed",
                extra={"batch_id": batch_id, "errors": error_info},
            )
            raise ProviderError(f"Batch job {status}: {error_info}")

        elapsed = loop.time() - start_time
        if elapsed > timeout:
            raise ProviderError(f"Batch timeout after {timeout}s")

        await asyncio.sleep(poll_interval)


async def cleanup_uploaded_files(client: AsyncOpenAI, file_ids: Iterable[str]) -> None:
    """Delete uploaded files from OpenAI once finished."""

    for file_id in file_ids:
        if not file_id:
            continue
        try:
            await client.files.delete(file_id)
            logger.debug("Deleted remote file", extra={"file_id": file_id})
        except Exception:  # pragma: no cover - cleanup best-effort
            logger.warning(
                "Failed to delete remote file", extra={"file_id": file_id}, exc_info=True
            )


__all__ = [
    "upload_batch_file",
    "create_remote_batch_job",
    "wait_for_batch_completion",
    "cleanup_uploaded_files",
]
