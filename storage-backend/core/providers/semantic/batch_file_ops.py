"""Local file helpers for OpenAI Batch API requests."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Iterable

from openai import AsyncOpenAI

from core.exceptions import ProviderError

from .batch_models import BatchRequest, BatchResult

logger = logging.getLogger(__name__)


def build_batch_file(
    requests: Iterable[BatchRequest],
    *,
    model: str,
    dimensions: int,
    output_path: Path | None = None,
) -> Path:
    """Create JSONL file consumed by the Batch API."""

    requests = list(requests)
    if not requests:
        raise ValueError("No requests provided")

    if output_path is None:
        fd, temp_path = tempfile.mkstemp(suffix=".jsonl", prefix="embeddings_batch_")
        os.close(fd)
        output_path = Path(temp_path)
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as handle:
        for request in requests:
            handle.write(
                json.dumps(
                    {
                        "custom_id": request.custom_id,
                        "method": "POST",
                        "url": "/v1/embeddings",
                        "body": {
                            "model": model,
                            "input": request.input_text,
                            "dimensions": dimensions,
                        },
                    }
                )
            )
            handle.write("\n")

    logger.info(
        "Created batch file",
        extra={
            "path": str(output_path),
            "request_count": len(requests),
            "size_bytes": output_path.stat().st_size,
        },
    )
    return output_path


async def download_batch_results_file(
    client: AsyncOpenAI,
    output_file_id: str,
    output_path: Path | None = None,
) -> Path:
    """Download batch results JSONL file."""

    try:
        content = await client.files.content(output_file_id)
        data = await content.aread()
    except Exception as exc:  # pragma: no cover - network failure
        logger.error("Failed to download results", exc_info=True)
        raise ProviderError(f"Results download failed: {exc}") from exc

    if output_path is None:
        fd, temp_path = tempfile.mkstemp(suffix=".jsonl", prefix="embeddings_results_")
        os.close(fd)
        output_path = Path(temp_path)
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_bytes(data)
    logger.info(
        "Downloaded batch results",
        extra={"output_file_id": output_file_id, "path": str(output_path)},
    )
    return output_path


def parse_batch_results(results_path: Path) -> list[BatchResult]:
    """Parse the results JSONL file into BatchResult objects."""

    results: list[BatchResult] = []
    with results_path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                logger.error(
                    "Failed to decode batch result line",
                    extra={"line": line_number},
                    exc_info=True,
                )
                continue

            custom_id = payload.get("custom_id")
            response = payload.get("response", {})
            if not custom_id:
                logger.warning(
                    "Result missing custom_id", extra={"line": line_number}
                )
                continue

            if response.get("status_code") == 200:
                body = response.get("body", {})
                embedding = body.get("data", [{}])[0].get("embedding", [])
                results.append(BatchResult(custom_id=str(custom_id), embedding=list(embedding)))
            else:
                error = (
                    response.get("body", {})
                    .get("error", {})
                    .get("message", "Unknown error")
                )
                results.append(
                    BatchResult(
                        custom_id=str(custom_id),
                        embedding=[],
                        error=str(error),
                    )
                )
                logger.warning(
                    "Batch result error",
                    extra={"custom_id": custom_id, "error": error},
                )

    logger.info("Parsed batch results", extra={"total": len(results)})
    return results


__all__ = [
    "build_batch_file",
    "download_batch_results_file",
    "parse_batch_results",
]
