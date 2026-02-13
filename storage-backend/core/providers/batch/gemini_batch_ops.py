"""Google Gemini Batch API helper operations."""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from google import genai  # type: ignore
from google.genai import types  # type: ignore

from config.batch.defaults import (
    BATCH_POLLING_INTERVAL_SECONDS,
    BATCH_TIMEOUT_SECONDS,
)
from core.exceptions import ProviderError

import logging

logger = logging.getLogger(__name__)


class GeminiBatchOperations:
    """Encapsulates Google Gemini Batch API workflows."""

    def __init__(self, client: genai.Client) -> None:  # type: ignore[type-arg]
        self.client = client

    async def _run_in_thread(self, func, *args, **kwargs):
        return await asyncio.to_thread(func, *args, **kwargs)

    async def create_jsonl_file(self, requests: List[Dict[str, Any]]) -> Path:
        """Create a JSONL file that can be uploaded via the Files API."""

        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        try:
            for request in requests:
                if "key" not in request:
                    raise ProviderError("Gemini batch request missing key", provider="google")
                temp_file.write(json.dumps(request) + "\n")
        finally:
            temp_file.close()

        return Path(temp_file.name)

    async def upload_file(self, file_path: Path) -> str:
        """Upload the batch request file and return its identifier."""

        logger.info("Uploading Gemini batch file %s", file_path)

        def _upload():
            return self.client.files.upload(
                file=str(file_path),
                config=types.UploadFileConfig(display_name="batch-requests", mime_type="application/jsonl"),
            )

        try:
            uploaded_file = await self._run_in_thread(_upload)
        except Exception as exc:  # pragma: no cover - network failure
            logger.exception("Failed to upload Gemini batch file")
            raise ProviderError("Gemini batch file upload failed", provider="google", original_error=exc) from exc

        logger.info("Uploaded Gemini batch file %s", uploaded_file.name)
        return uploaded_file.name

    async def submit_inline_batch(
        self,
        *,
        model: str,
        requests: List[Dict[str, Any]],
        display_name: Optional[str] = None,
    ) -> str:
        """Submit a batch request payload directly."""

        logger.info("Submitting Gemini inline batch (%d requests)", len(requests))

        # For inline requests, validate GenerateContentRequest structure (not key/request wrapper)
        for idx, req in enumerate(requests):
            if "contents" not in req:
                raise ProviderError(
                    f"Request {idx} missing 'contents' field (GenerateContentRequest required)",
                    provider="google",
                )
            logger.debug("Validated Gemini inline batch request", extra={"request_idx": idx})

        def _create():
            return self.client.batches.create(
                model=model,
                src=requests,
                config={"display_name": display_name or "text-generation-batch"},
            )

        try:
            batch_job = await self._run_in_thread(_create)
        except Exception as exc:  # pragma: no cover - network failure
            logger.exception("Failed to create Gemini inline batch")
            raise ProviderError("Gemini batch creation failed", provider="google", original_error=exc) from exc

        logger.info("Created Gemini batch %s", batch_job.name)
        return batch_job.name

    async def submit_file_batch(
        self,
        *,
        model: str,
        file_path: Path,
        display_name: Optional[str] = None,
    ) -> str:
        """Upload a JSONL file and submit a batch job."""

        file_name = await self.upload_file(file_path)

        def _create():
            return self.client.batches.create(
                model=model,
                src=file_name,
                config={"display_name": display_name or "text-generation-batch"},
            )

        logger.info("Submitting Gemini batch from uploaded file")
        try:
            batch_job = await self._run_in_thread(_create)
        except Exception as exc:  # pragma: no cover - network failure
            logger.exception("Failed to create Gemini file batch")
            raise ProviderError("Gemini batch creation failed", provider="google", original_error=exc) from exc

        logger.info("Created Gemini batch %s", batch_job.name)
        return batch_job.name

    async def poll_batch_status(
        self,
        batch_name: str,
        *,
        polling_interval: int = BATCH_POLLING_INTERVAL_SECONDS,
        timeout: int = BATCH_TIMEOUT_SECONDS,
    ) -> Dict[str, Any]:
        """Poll a Gemini batch job until it reaches a terminal state."""

        logger.info("Polling Gemini batch %s", batch_name)
        loop = asyncio.get_running_loop()
        start_time = loop.time()

        completed_states = {
            "JOB_STATE_SUCCEEDED",
            "JOB_STATE_FAILED",
            "JOB_STATE_CANCELLED",
            "JOB_STATE_EXPIRED",
        }

        while True:
            try:
                batch_job = await self._run_in_thread(lambda: self.client.batches.get(name=batch_name))
            except Exception as exc:  # pragma: no cover - network failure
                logger.exception("Failed to retrieve Gemini batch status")
                raise ProviderError("Gemini batch polling failed", provider="google", original_error=exc) from exc

            state_name = getattr(getattr(batch_job, "state", None), "name", None)
            logger.debug("Gemini batch %s state: %s", batch_name, state_name)

            if state_name in completed_states:
                if state_name != "JOB_STATE_SUCCEEDED":
                    raise ProviderError(f"Gemini batch ended with state {state_name}", provider="google")

                return {
                    "name": batch_job.name,
                    "state": state_name,
                    "dest": getattr(batch_job, "dest", None),
                }

            elapsed = loop.time() - start_time
            if elapsed > timeout:
                raise ProviderError(f"Batch {batch_name} polling timeout after {timeout}s", provider="google")

            await asyncio.sleep(polling_interval)

    async def download_results(self, destination: Any) -> List[Dict[str, Any]]:
        """Download Gemini batch results."""

        results: List[Dict[str, Any]] = []
        if hasattr(destination, "inlined_responses") and destination.inlined_responses:
            logger.info("Processing inline Gemini batch results")
            for response in destination.inlined_responses:
                results.append(
                    {
                        "key": getattr(response, "key", None),
                        "response": getattr(response, "response", None),
                        "error": getattr(response, "error", None),
                    }
                )
            return results

        file_name = getattr(destination, "file_name", None)
        if not file_name:
            logger.info("No Gemini batch results to download")
            return results

        logger.info("Downloading Gemini batch results from file %s", file_name)

        def _download():
            return self.client.files.download(file=file_name)

        try:
            file_content = await self._run_in_thread(_download)
        except Exception as exc:  # pragma: no cover - network failure
            logger.exception("Failed to download Gemini batch results")
            raise ProviderError("Gemini batch result download failed", provider="google", original_error=exc) from exc

        content = file_content.decode("utf-8") if isinstance(file_content, bytes) else str(file_content)
        for line in content.strip().split("\n"):
            if not line:
                continue
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                logger.debug("Skipping invalid Gemini batch result line: %s", line)

        return results

    async def submit_and_wait(
        self,
        *,
        model: str,
        requests: List[Dict[str, Any]],
        use_file: bool = False,
    ) -> List[Dict[str, Any]]:
        """Submit a Gemini batch job and wait for the final results."""

        if use_file:
            file_path = await self.create_jsonl_file(requests)
            try:
                batch_name = await self.submit_file_batch(model=model, file_path=file_path)
            finally:
                file_path.unlink(missing_ok=True)
        else:
            batch_name = await self.submit_inline_batch(model=model, requests=requests)

        batch_result = await self.poll_batch_status(batch_name)
        return await self.download_results(batch_result.get("dest"))


__all__ = ["GeminiBatchOperations"]
