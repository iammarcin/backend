"""Administrative endpoints exposing model registry information."""

from __future__ import annotations

import logging
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from config.audio.providers.openai import STREAMING_TRANSCRIPTION_MODEL_NAMES
from config.realtime.providers.openai import REALTIME_MODELS
from config.text.providers.openai.models import (
    OPENAI_MODELS,
    get_model_config,
    get_model_voices,
    list_models_by_category,
)
from core.auth import AuthContext, require_auth_context
from core.providers.registry.model_config import ModelConfig
from core.pydantic_schemas import ok as api_ok

logger = logging.getLogger(__name__)

# Directory for uploaded mobile logs (mounted via docker-compose)
LOGS_UPLOAD_DIR = Path(os.environ.get("MOBILE_LOGS_DIR", "/logs"))

router = APIRouter(prefix="/admin", tags=["admin"])


def _model_config_to_dict(config: ModelConfig) -> dict[str, Any]:
    """Serialise ModelConfig instances into JSON-friendly dictionaries."""

    payload = asdict(config)
    voices = payload.get("voices")
    if isinstance(voices, tuple):
        payload["voices"] = list(voices)
    return payload


@router.get("/models/openai")
async def list_openai_models() -> dict[str, Any]:
    """Return the full set of registered OpenAI models."""

    return {
        "total": len(OPENAI_MODELS),
        "models": {model: _model_config_to_dict(config) for model, config in OPENAI_MODELS.items()},
    }


@router.get("/models/openai/realtime")
async def list_openai_realtime_models() -> dict[str, Any]:
    """Return registered OpenAI realtime (speech-to-speech) models."""

    models = list(REALTIME_MODELS.keys())
    return {"models": models, "count": len(models)}


@router.get("/models/openai/transcription")
async def list_openai_transcription_models() -> dict[str, Any]:
    """Return registered OpenAI streaming transcription models."""

    models = list(STREAMING_TRANSCRIPTION_MODEL_NAMES)
    return {"models": models, "count": len(models)}


@router.get("/models/openai/by-category/{category}")
async def list_openai_models_by_category(category: str) -> dict[str, Any]:
    """Return OpenAI models filtered by category."""

    models = list_models_by_category(category)
    if not models:
        raise HTTPException(status_code=404, detail=f"No models found for category '{category}'")
    return {"models": models, "count": len(models)}


@router.get("/models/openai/{model}")
async def get_openai_model_details(model: str) -> dict[str, Any]:
    """Return detailed configuration for a specific OpenAI model."""

    config = get_model_config(model)
    if config is None:
        raise HTTPException(status_code=404, detail=f"Model '{model}' not found")

    response = {
        "model": model,
        "config": _model_config_to_dict(config),
    }
    voices = get_model_voices(model)
    if voices:
        response["voices"] = list(voices)
    return response


@router.post("/logs/upload")
async def upload_mobile_logs(
    file: UploadFile = File(..., description="Log file from mobile app"),
    auth_context: AuthContext = Depends(require_auth_context),
) -> JSONResponse:
    """Upload mobile app logs for debugging.

    Saves log files to the configured logs directory with timestamp prefix.
    """
    LOGS_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    filename = file.filename or "unknown.txt"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    user_id = auth_context.get("user_id", "unknown")
    safe_filename = f"{timestamp}_user{user_id}_{filename}"

    file_bytes = await file.read()
    await file.close()

    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    dest_path = LOGS_UPLOAD_DIR / safe_filename
    dest_path.write_bytes(file_bytes)

    logger.info(
        "Mobile logs uploaded (user_id=%s, filename=%s, size=%d bytes)",
        user_id,
        safe_filename,
        len(file_bytes),
    )

    return JSONResponse(
        status_code=200,
        content=api_ok(
            "Logs uploaded successfully",
            data={"filename": safe_filename, "size": len(file_bytes)},
        ),
    )


__all__ = ["router"]
