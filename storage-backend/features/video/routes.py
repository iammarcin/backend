"""Video generation HTTP routes."""

from __future__ import annotations

import base64
import logging

from fastapi import APIRouter, Depends, HTTPException

from core.exceptions import (
    ConfigurationError,
    ProviderError,
    ServiceError,
    ValidationError,
)
from core.pydantic_schemas import APIResponse, VideoGenerationRequest, VideoGenerationResponse
from core.auth import AuthContext, require_auth_context
from core.http.errors import (
    format_configuration_error,
    format_provider_error,
    format_service_error,
    format_validation_error,
)
from features.video.service import VideoService

router = APIRouter(prefix="/video", tags=["video"])
logger = logging.getLogger(__name__)


def _prompt_preview(prompt: str) -> str:
    text = (prompt or "").strip().replace("\n", " ")
    return text[:120] + ("…" if len(text) > 120 else "")


@router.post("/generate", response_model=APIResponse)
async def generate_video(
    request: VideoGenerationRequest,
    auth_context: AuthContext = Depends(require_auth_context),
) -> APIResponse:
    """Generate a video from text or image input."""

    service = VideoService()

    logger.info(
        "POST /video/generate received (customer_id=%s, save_to_db=%s, prompt='%s', has_image=%s)",
        request.customer_id,
        request.save_to_db,
        _prompt_preview(request.prompt),
        bool(request.input_image_url),
    )
    logger.debug(
        "Authenticated video generation request (token_customer_id=%s)",
        auth_context["customer_id"],
    )
    if request.settings:
        logger.debug("/video/generate settings: %s", request.settings)

    try:
        result = await service.generate(
            prompt=request.prompt,
            settings=request.settings,
            customer_id=request.customer_id,
            input_image_url=request.input_image_url,
            save_to_s3=request.save_to_db,
        )
    except ValidationError as exc:
        logger.warning("Validation error in /video/generate: %s", exc)
        raise HTTPException(
            status_code=400,
            detail=format_validation_error(exc),
        ) from exc
    except ConfigurationError as exc:
        logger.warning("Configuration error in /video/generate: %s", exc)
        raise HTTPException(
            status_code=400,
            detail=format_configuration_error(exc),
        ) from exc
    except NotImplementedError as exc:
        logger.info("Video provider not implemented: %s", exc)
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except ProviderError as exc:
        logger.error("Provider error in /video/generate: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=format_provider_error(exc),
        ) from exc
    except ServiceError as exc:
        logger.error("Storage error in /video/generate: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=format_service_error(exc),
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Unexpected error in /video/generate: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error") from exc

    video_url = result.get("video_url")
    if not video_url:
        video_bytes = result.get("video_bytes")
        if video_bytes:
            video_url = "data:video/mp4;base64," + base64.b64encode(video_bytes).decode("utf-8")
        else:
            raise HTTPException(status_code=502, detail="Video generation returned no data")

    metadata = result.get("settings", {})

    response = VideoGenerationResponse(
        video_url=video_url,
        provider=metadata.get("provider", "video"),
        model=metadata.get("model", "veo-3.1-fast"),
        duration=metadata.get("duration_seconds", result.get("duration", 5)),
        settings=metadata,
    )

    logger.info(
        "Video generation successful (customer_id=%s, provider=%s, model=%s, mode=%s)",
        request.customer_id,
        metadata.get("provider"),
        metadata.get("model"),
        metadata.get("mode"),
    )
    return APIResponse(success=True, data=response.model_dump(), code=200)


@router.post("/extend", response_model=APIResponse)
async def extend_video(
    request: VideoGenerationRequest,
    auth_context: AuthContext = Depends(require_auth_context),
) -> APIResponse:
    """Extend an existing video."""

    service = VideoService()

    logger.info(
        "POST /video/extend received (customer_id=%s, save_to_db=%s, video_id=%s)",
        request.customer_id,
        request.save_to_db,
        request.settings.get("video_id") if request.settings else None,
    )
    logger.debug(
        "Authenticated video extension request (token_customer_id=%s)",
        auth_context["customer_id"],
    )
    if request.settings:
        logger.debug("/video/extend settings: %s", request.settings)

    try:
        # Extract video_id from settings
        video_id = None
        if request.settings and "video" in request.settings:
            video_id = request.settings["video"].get("video_id")
        elif request.settings and "video_id" in request.settings:
            video_id = request.settings["video_id"]

        if not video_id:
            raise HTTPException(
                status_code=400,
                detail="video_id is required in settings"
            )

        result = await service.extend_video(
            video_id=video_id,
            prompt=request.prompt,
            settings=request.settings,
            customer_id=request.customer_id,
            save_to_s3=request.save_to_db,
        )
    except ValidationError as exc:
        logger.warning("Validation error in /video/extend: %s", exc)
        raise HTTPException(
            status_code=400,
            detail=format_validation_error(exc),
        ) from exc
    except NotImplementedError as exc:
        logger.info("Video extension not implemented: %s", exc)
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except ProviderError as exc:
        logger.error("Provider error in /video/extend: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=format_provider_error(exc),
        ) from exc
    except ServiceError as exc:
        logger.error("Storage error in /video/extend: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=format_service_error(exc),
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Unexpected error in /video/extend: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error") from exc

    video_url = result.get("video_url")
    if not video_url:
        video_bytes = result.get("video_bytes")
        if video_bytes:
            video_url = "data:video/mp4;base64," + base64.b64encode(video_bytes).decode("utf-8")
        else:
            raise HTTPException(status_code=502, detail="Video extension returned no data")

    metadata = result.get("settings", {})

    response = VideoGenerationResponse(
        video_url=video_url,
        provider=metadata.get("provider", "video"),
        model=metadata.get("model", "kling-v1"),
        duration=metadata.get("duration_seconds", 5),
        settings=metadata,
    )

    logger.info(
        "Video extension successful (customer_id=%s, provider=%s, source_video_id=%s)",
        request.customer_id,
        metadata.get("provider"),
        result.get("source_video_id"),
    )
    return APIResponse(success=True, data=response.model_dump(), code=200)
