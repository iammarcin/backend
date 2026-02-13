"""Image generation HTTP routes."""

from __future__ import annotations

import base64
import logging

from fastapi import APIRouter, Depends, HTTPException

from core.exceptions import ProviderError, ServiceError, ValidationError
from core.pydantic_schemas import APIResponse, ImageGenerationRequest, ImageGenerationResponse
from features.image.service import ImageService
from core.auth import AuthContext, require_auth_context
from core.http.errors import (
    format_provider_error,
    format_service_error,
    format_validation_error,
)

router = APIRouter(prefix="/image", tags=["image"])
logger = logging.getLogger(__name__)


def _prompt_preview(prompt: str) -> str:
    text = (prompt or "").strip().replace("\n", " ")
    return text[:120] + ("…" if len(text) > 120 else "")


@router.post("/generate", response_model=APIResponse)
async def generate_image(
    request: ImageGenerationRequest,
    auth_context: AuthContext = Depends(require_auth_context),
) -> APIResponse:
    """Generate an image from a text prompt."""

    service = ImageService()

    logger.info(
        "POST /image/generate received (customer_id=%s, save_to_db=%s, prompt='%s')",
        request.customer_id,
        request.save_to_db,
        _prompt_preview(request.prompt),
    )
    logger.debug(
        "Authenticated image generation request (token_customer_id=%s)",
        auth_context["customer_id"],
    )
    if request.settings:
        logger.debug("/image/generate settings: %s", request.settings)

    try:
        s3_url, image_bytes, metadata = await service.generate_image(
            prompt=request.prompt,
            settings=request.settings,
            customer_id=request.customer_id,
            save_to_s3=request.save_to_db,
            input_image_url=request.image_url,
        )
    except ValidationError as exc:
        logger.warning("Validation error in /image/generate: %s", exc)
        raise HTTPException(
            status_code=400,
            detail=format_validation_error(exc),
        ) from exc
    except ProviderError as exc:
        logger.error("Provider error in /image/generate: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=format_provider_error(exc),
        ) from exc
    except ServiceError as exc:
        logger.error("Storage error in /image/generate: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=format_service_error(exc),
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Unexpected error in /image/generate: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error") from exc

    if s3_url:
        image_url = s3_url
    else:
        image_url = "data:image/png;base64," + base64.b64encode(image_bytes).decode("utf-8")

    response = ImageGenerationResponse(
        image_url=image_url,
        provider=metadata["provider"],
        model=metadata["model"],
        settings=metadata,
    )

    logger.info(
        "Image generation successful (customer_id=%s, provider=%s, model=%s)",
        request.customer_id,
        response.provider,
        response.model,
    )
    return APIResponse(success=True, data=response.model_dump(), code=200)

