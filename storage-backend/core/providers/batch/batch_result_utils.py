"""Utilities for batch result processing."""

import json
import logging
from typing import Any, Dict, List

from openai import AsyncOpenAI

from core.exceptions import ProviderError

logger = logging.getLogger(__name__)


async def download_batch_results(client: AsyncOpenAI, output_file_id: str) -> List[Dict[str, Any]]:
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
        response = await client.files.content(output_file_id)
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


async def process_batch_error_file(client: AsyncOpenAI, error_file_id: str, batch_id: str) -> List[str]:
    """Download and process batch error file, returning error messages."""

    logger.info("Attempting to download error file", extra={"error_file_id": error_file_id})
    try:
        error_content = await download_batch_results(client, error_file_id)
        logger.info(f"Downloaded {len(error_content)} error entries")

        # DEBUG: Print raw error content to see actual structure
        print(f"\n=== RAW ERROR FILE CONTENT ({len(error_content)} entries) ===")
        for idx, entry in enumerate(error_content):
            print(f"Entry {idx}: {json.dumps(entry, indent=2)}")
        print("=== END RAW ERROR CONTENT ===\n")

        # Parse and display each error clearly
        error_messages = []
        for idx, error_entry in enumerate(error_content):
            custom_id = error_entry.get("custom_id", f"request-{idx}")

            # OpenAI error file format: error is in response.body.error, NOT root error field
            response = error_entry.get("response", {})
            body = response.get("body", {}) if isinstance(response, dict) else {}
            error_obj = body.get("error", {}) if isinstance(body, dict) else {}

            # Extract error details
            error_type = error_obj.get("type", "unknown")
            error_msg = error_obj.get("message", "No error details")
            error_code = error_obj.get("code", "N/A")

            error_messages.append(f"{custom_id}: [{error_type}] {error_msg}")

            # Print to stdout for script execution
            print(f"ERROR in batch request '{custom_id}':")
            print(f"  Type: {error_type}")
            print(f"  Code: {error_code}")
            print(f"  Message: {error_msg}")
            print(f"  Full error: {error_obj}")
            print()

            logger.error(
                f"Batch request failed: {custom_id}",
                extra={
                    "custom_id": custom_id,
                    "error_type": error_type,
                    "error_code": error_code,
                    "error_message": error_msg,
                    "full_error": error_obj,
                },
            )

        # Log summary
        print(f"\nBatch {batch_id} completed with {len(error_content)} errors:")
        for msg in error_messages:
            print(f"  - {msg}")
        print()

        logger.error(
            "Batch completed with errors",
            extra={
                "batch_id": batch_id,
                "error_file_id": error_file_id,
                "total_errors": len(error_content),
                "error_summary": error_messages,
            },
        )

        return error_messages

    except Exception as exc:  # pragma: no cover - diagnostics only
        import traceback
        print(f"FAILED to download/parse error file:")
        print(f"  Error file ID: {error_file_id}")
        print(f"  Exception: {exc}")
        print(f"  Traceback: {traceback.format_exc()}")
        print()

        logger.error(
            "Failed to download/parse error file",
            extra={
                "batch_id": batch_id,
                "error_file_id": error_file_id,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            },
        )
        raise


__all__ = ["download_batch_results", "process_batch_error_file"]