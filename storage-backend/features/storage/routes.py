"""HTTP endpoints for S3-backed storage operations."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import JSONResponse

from core.auth import AuthContext, require_auth_context
from core.exceptions import ServiceError
from core.pydantic_schemas import ApiResponse, error as api_error, ok as api_ok
from infrastructure.aws.storage import StorageService

from .dependencies import get_storage_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/storage", tags=["Storage"])

ALLOWED_FILE_EXTENSIONS: frozenset[str] = frozenset(
    {
        "jpg",
        "jpeg",
        "png",
        "gif",
        "mp3",
        "pcm",
        "mpeg",
        "mpga",
        "webm",
        "webp",
        "wav",
        "m4a",
        "txt",
        "mp4",
        "opus",
        "pdf",
    }
)


def _parse_json_field(raw_value: str | None, field: str) -> Dict[str, Any]:
    """Parse a JSON-encoded form field, returning an empty dict on blank input."""

    if not raw_value:
        return {}
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive guard
        logger.debug("Invalid JSON for field %s: %s", field, raw_value)
        raise ValueError(field) from exc

    if isinstance(parsed, dict):
        return parsed
    logger.debug("Ignoring non-object JSON payload for %s", field)
    return {}


@router.post(
    "/upload",
    response_model=ApiResponse[Dict[str, str]],
    summary="Upload a chat attachment to persistent storage",
)
async def upload_attachment(
    file: UploadFile = File(..., description="File selected by the user"),
    category: str = Form(...),
    action: str = Form(...),
    customer_id: int = Form(...),
    user_input: str | None = Form(None),
    user_settings: str | None = Form(None),
    asset_input: str | None = Form(None),
    auth_context: AuthContext = Depends(require_auth_context),
    storage: StorageService = Depends(get_storage_service),
) -> JSONResponse:
    """Persist a chat attachment to S3 and return the public URL."""

    logger.debug(
        "Authenticated storage upload request (customer_id=%s)",
        auth_context["customer_id"],
    )

    try:
        user_input_parsed = _parse_json_field(user_input, "user_input")
        _parse_json_field(user_settings, "user_settings")
        if asset_input:
            _parse_json_field(asset_input, "asset_input")
    except ValueError as exc:
        field = str(exc)
        logger.debug("Storage upload rejected due to invalid JSON in %s", field)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=api_error(
                400,
                f"Invalid JSON payload for {field}",
                data={"field": field},
            ),
        )

    filename = file.filename or "upload.bin"
    extension = Path(filename).suffix.lstrip(".").lower()
    if extension not in ALLOWED_FILE_EXTENSIONS:
        logger.info(
            "Upload rejected due to unsupported extension: %s (customer_id=%s)",
            extension or "<none>",
            customer_id,
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=api_error(
                400,
                "Only files with specific extensions are allowed!",
                data={"extension": extension},
            ),
        )

    file_bytes = await file.read()
    await file.close()
    if not file_bytes:
        logger.debug(
            "Received empty file for chat attachment (customer_id=%s, filename=%s)",
            customer_id,
            filename,
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=api_error(400, "Uploaded file is empty"),
        )

    force_filename = bool(user_input_parsed.get("force_filename"))

    logger.info(
        "Uploading chat attachment (customer_id=%s, filename=%s, content_type=%s, size=%s)",
        customer_id,
        filename,
        file.content_type,
        len(file_bytes),
    )

    try:
        url = await storage.upload_chat_attachment(
            file_bytes=file_bytes,
            customer_id=customer_id,
            filename=filename,
            content_type=file.content_type,
            force_filename=force_filename,
        )
    except ServiceError as exc:
        logger.error("Chat attachment upload failed: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content=api_error(502, str(exc)),
        )
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.error("Unexpected error during attachment upload: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=api_error(500, "Internal server error"),
        )

    stored_filename = url.rsplit("/", 1)[-1]
    payload = {"url": url, "result": url, "filename": stored_filename}
    meta = {
        "category": category,
        "action": action,
        "extension": extension,
        "content_type": file.content_type,
    }

    logger.info(
        "Chat attachment uploaded (customer_id=%s, stored_filename=%s)",
        customer_id,
        stored_filename,
    )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=api_ok("File uploaded successfully", data=payload, meta=meta),
    )


__all__ = ["router"]
