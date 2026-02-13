"""File operations for batch processing."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from openai import AsyncOpenAI

from core.exceptions import ProviderError

logger = logging.getLogger(__name__)


class BatchFileOperations:
    """Handles file operations for OpenAI batch processing."""

    def __init__(self, client: AsyncOpenAI) -> None:
        self.client = client

    async def create_jsonl_file(
        self,
        requests: List[Dict[str, Any]],
        endpoint: str = "https://api.openai.com/v1/chat/completions",
    ) -> Path:
        """Create a JSONL file formatted for OpenAI batch submission."""

        logger.info(
            "Creating JSONL batch payload",
            extra={
                "request_count": len(requests),
                "endpoint": endpoint,
            },
        )

        temp_file = Path("/tmp") / f"batch_{id(self)}.jsonl"
        temp_file.parent.mkdir(exist_ok=True)

        try:
            with temp_file.open("w") as f:
                for request in requests:
                    custom_id = request.get("custom_id")
                    if not custom_id:
                        raise ProviderError("Batch request missing custom_id", provider="openai")

                    body = request.get("body") or {}
                    batch_request = {
                        "custom_id": custom_id,
                        "method": "POST",
                        "url": endpoint,
                        "body": body,
                    }
                    f.write(json.dumps(batch_request) + "\n")
        except Exception:
            temp_file.unlink(missing_ok=True)
            raise

        logger.info(
            "JSONL batch payload created",
            extra={
                "path": str(temp_file),
                "request_count": len(requests),
            },
        )
        return temp_file

    async def upload_batch_file(self, file_path: Path) -> str:
        """Upload JSONL payload and return file identifier."""

        logger.info(
            "Uploading batch file",
            extra={"file_path": str(file_path)},
        )
        try:
            with file_path.open("rb") as handle:
                file_object = await self.client.files.create(file=handle, purpose="batch")
        except Exception as exc:  # pragma: no cover - network failure
            logger.exception("Failed to upload batch file")
            raise ProviderError(f"Batch file upload failed: {exc}", provider="openai") from exc

        logger.info(
            "Batch file uploaded",
            extra={"file_path": str(file_path), "file_id": file_object.id},
        )
        return file_object.id

    async def cleanup_file(self, file_id: str | None) -> None:
        """Delete an uploaded file."""

        if not file_id:
            return
        try:
            await self.client.files.delete(file_id)
        except Exception:  # pragma: no cover - best-effort cleanup
            logger.warning("Failed to delete OpenAI file %s", file_id)


__all__ = ["BatchFileOperations"]