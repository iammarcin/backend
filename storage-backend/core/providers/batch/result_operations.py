"""Result operations for batch processing."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from openai import AsyncOpenAI

from core.exceptions import ProviderError

logger = logging.getLogger(__name__)


class BatchResultOperations:
    """Handles result operations for OpenAI batch processing."""

    def __init__(self, client: AsyncOpenAI) -> None:
        self.client = client

    async def download_results(self, output_file_id: str) -> List[Dict[str, Any]]:
        """Download and parse batch results from OpenAI."""

        if not output_file_id:
            error_msg = "No output_file_id provided - cannot download results"
            logger.error(error_msg)
            raise ProviderError(error_msg, provider="openai")

        logger.info(
            "Downloading batch results",
            extra={"output_file_id": output_file_id},
        )
        try:
            response = await self.client.files.content(output_file_id)
        except Exception as exc:  # pragma: no cover - network failure
            logger.exception(
                "Failed to download batch results",
                extra={"output_file_id": output_file_id},
            )
            raise ProviderError("Failed to download batch results", provider="openai") from exc

        text = getattr(response, "text", None)
        if text is None and hasattr(response, "read"):
            text = await response.read()
        if isinstance(text, bytes):
            text = text.decode("utf-8")
        if not isinstance(text, str):
            text = ""

        logger.info(
            "Downloaded batch results",
            extra={
                "output_file_id": output_file_id,
                "content_length": len(text),
            },
        )

        results: List[Dict[str, Any]] = []
        for line_number, line in enumerate(text.strip().split("\n"), start=1):
            if not line:
                continue
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                logger.warning(
                    "Failed to parse batch result line",
                    extra={
                        "output_file_id": output_file_id,
                        "line_number": line_number,
                        "line_preview": line[:100],
                    },
                )

        logger.info(
            "Parsed batch results",
            extra={
                "output_file_id": output_file_id,
                "total_results": len(results),
            },
        )

        return results


__all__ = ["BatchResultOperations"]