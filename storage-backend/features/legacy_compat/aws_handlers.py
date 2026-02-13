"""
Handler functions for legacy /api/aws endpoint actions.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import UploadFile
from fastapi.responses import JSONResponse

from infrastructure.aws.storage import StorageService
from .response_helpers import legacy_error_response, legacy_success_response

logger = logging.getLogger(__name__)

# Allowed file extensions for upload
ALLOWED_EXTENSIONS = {
    "jpg", "jpeg", "png", "gif", "mp3", "pcm", "mpeg",
    "mpga", "webm", "webp", "wav", "m4a", "txt", "mp4", "opus", "pdf"
}


async def handle_aws_upload(
    action: str,
    category: str,
    user_input: str,
    customer_id: int,
    file: UploadFile,
    storage: StorageService,
) -> JSONResponse:
    """
    Handle legacy AWS file upload.

    Handles file uploads (images, audio, etc.) and stores them in S3.

    Args:
        action: The upload action (for logging)
        category: File category (for logging)
        user_input: JSON string containing user input parameters
        customer_id: Customer ID for file organization
        file: The uploaded file
        storage: Storage service for S3 operations

    Returns:
        JSONResponse with upload result
    """
    logger.info(
        f"Legacy AWS upload: action={action}, category={category}, "
        f"customer_id={customer_id}, filename={file.filename}"
    )

    # Parse user input JSON
    try:
        user_input_dict = json.loads(user_input) if user_input else {}
    except json.JSONDecodeError:
        logger.error("Invalid JSON in user_input field")
        return legacy_error_response("Invalid JSON in user_input", 400)

    # Validate file
    filename = file.filename or "upload.bin"
    extension = Path(filename).suffix.lstrip(".").lower()

    if extension not in ALLOWED_EXTENSIONS:
        logger.warning(f"Unsupported file extension: {extension}")
        return legacy_error_response(
            f"File extension .{extension} is not allowed",
            400
        )

    # Read file content
    try:
        file_bytes = await file.read()
        await file.close()
    except Exception as e:
        logger.error(f"Failed to read uploaded file: {e}")
        return legacy_error_response("Failed to read uploaded file", 500)

    if not file_bytes:
        logger.warning("Uploaded file is empty")
        return legacy_error_response("Uploaded file is empty", 400)

    # Upload to S3
    try:
        force_filename = bool(user_input_dict.get("force_filename", False))

        url = await storage.upload_chat_attachment(
            file_bytes=file_bytes,
            customer_id=customer_id,
            filename=filename,
            content_type=file.content_type,
            force_filename=force_filename,
        )

        stored_filename = url.rsplit("/", 1)[-1]

        logger.info(f"File uploaded successfully: {stored_filename}")

        # Return in legacy format - just the URL as the result
        return legacy_success_response(url)

    except Exception as e:
        logger.error(f"Failed to upload file to storage: {e}", exc_info=True)
        return legacy_error_response(f"Failed to upload file: {str(e)}", 500)


__all__ = ["handle_aws_upload", "ALLOWED_EXTENSIONS"]
