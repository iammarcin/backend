"""OpenAI Batch API support for semantic search backfills."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from config.semantic_search.embeddings import (
    DIMENSIONS as DEFAULT_EMBEDDING_DIMENSIONS,
    MODEL as DEFAULT_EMBEDDING_MODEL,
)
from config.api_keys import OPENAI_API_KEY
from core.exceptions import ProviderError

from .batch_file_ops import (
    build_batch_file,
    download_batch_results_file,
    parse_batch_results,
)
from .batch_job_ops import (
    cleanup_uploaded_files,
    create_remote_batch_job,
    upload_batch_file,
    wait_for_batch_completion,
)
from .batch_models import BatchRequest, BatchResult

logger = logging.getLogger(__name__)


class BatchEmbeddingProvider:
    """Wrapper around the OpenAI Batch API for embeddings."""

    def __init__(
        self,
        *,
        client: AsyncOpenAI | None = None,
        api_key: str = OPENAI_API_KEY,
        model: str | None = None,
        dimensions: int | None = None,
    ) -> None:
        if client is None:
            if not api_key:
                raise ValueError("OpenAI API key is required")
            client = AsyncOpenAI(api_key=api_key)

        self.client = client
        self.model = model or DEFAULT_EMBEDDING_MODEL
        self.dimensions = dimensions or DEFAULT_EMBEDDING_DIMENSIONS

        logger.info(
            "Initialized Batch Embedding Provider",
            extra={"model": self.model, "dimensions": self.dimensions},
        )

    async def create_batch_file(
        self,
        requests: list[BatchRequest],
        output_path: Path | None = None,
    ) -> Path:
        return build_batch_file(
            requests,
            model=self.model,
            dimensions=self.dimensions,
            output_path=output_path,
        )

    async def upload_batch_file(self, file_path: Path) -> str:
        return await upload_batch_file(self.client, file_path)

    async def create_batch_job(
        self,
        input_file_id: str,
        *,
        description: str = "Semantic search embedding batch",
    ) -> str:
        return await create_remote_batch_job(
            self.client, input_file_id, description=description
        )

    async def wait_for_completion(
        self,
        batch_id: str,
        *,
        poll_interval: int = 10,
        timeout: int = 7200,
    ) -> dict[str, Any]:
        return await wait_for_batch_completion(
            self.client,
            batch_id,
            poll_interval=poll_interval,
            timeout=timeout,
        )

    async def download_results(
        self,
        output_file_id: str,
        output_path: Path | None = None,
    ) -> Path:
        return await download_batch_results_file(
            self.client, output_file_id, output_path
        )

    async def parse_results(self, results_path: Path) -> list[BatchResult]:
        return parse_batch_results(results_path)

    async def cleanup_files(self, file_ids: list[str]) -> None:
        await cleanup_uploaded_files(self.client, file_ids)

    async def generate_batch(
        self,
        requests: list[BatchRequest],
        *,
        cleanup: bool = True,
    ) -> list[BatchResult]:
        """Execute the complete Batch API workflow."""

        input_path = await self.create_batch_file(requests)
        input_file_id: str | None = None
        output_file_id: str | None = None
        output_path: Path | None = None

        try:
            input_file_id = await self.upload_batch_file(input_path)
            batch_id = await self.create_batch_job(input_file_id)
            result = await self.wait_for_completion(batch_id)
            output_file_id = result.get("output_file_id")
            if not output_file_id:
                raise ProviderError("Batch completed without output file id")

            output_path = await self.download_results(output_file_id)
            results = await self.parse_results(output_path)
        finally:
            input_path.unlink(missing_ok=True)

        if cleanup:
            await self.cleanup_files(
                [fid for fid in (input_file_id, output_file_id) if fid]
            )
            if output_path:
                output_path.unlink(missing_ok=True)

        return results


__all__ = ["BatchEmbeddingProvider", "BatchRequest", "BatchResult"]
