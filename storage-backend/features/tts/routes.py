"""REST routes exposing text-to-speech functionality."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse, StreamingResponse

from core.pydantic_schemas import error as api_error, ok as api_ok
from core.exceptions import ConfigurationError, ProviderError, ServiceError, ValidationError
from core.http.errors import (
    format_configuration_error,
    format_provider_error,
    format_service_error,
    format_validation_error,
)
from features.tts.dependencies import get_tts_service
from features.tts.schemas.requests import TTSAction, TTSGenerateRequest
from features.tts.schemas.responses import (
    TTSGenerateResponse,
    TTSMetadata,
    TTSSuccessMessage,
)
from features.tts.service import TTSService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tts", tags=["TTS"])


@router.post(
    "/generate",
    summary="Generate speech from text",
    response_model=TTSGenerateResponse,
)
async def generate_tts_endpoint(
    request: TTSGenerateRequest,
    service: TTSService = Depends(get_tts_service),
) -> JSONResponse:
    """Generate speech synchronously via the configured TTS provider."""

    if request.action is TTSAction.BILLING:
        return await _handle_billing_request(request, service)

    try:
        result = await service.generate(request)
    except ValidationError as exc:
        logger.warning("TTS validation error: %s", exc)
        payload = api_error(
            code=status.HTTP_400_BAD_REQUEST,
            message="Invalid TTS request",
            data=format_validation_error(exc),
        )
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=payload)
    except ConfigurationError as exc:
        logger.error("TTS configuration error: %s", exc)
        payload = api_error(
            code=status.HTTP_502_BAD_GATEWAY,
            message="TTS configuration error",
            data=format_configuration_error(exc),
        )
        return JSONResponse(status_code=status.HTTP_502_BAD_GATEWAY, content=payload)
    except ProviderError as exc:
        logger.error("TTS provider error: %s", exc)
        payload = api_error(
            code=status.HTTP_502_BAD_GATEWAY,
            message="TTS provider error",
            data=format_provider_error(exc),
        )
        return JSONResponse(status_code=status.HTTP_502_BAD_GATEWAY, content=payload)
    except ServiceError as exc:
        logger.error("TTS service error: %s", exc)
        payload = api_error(
            code=status.HTTP_502_BAD_GATEWAY,
            message="Failed to generate TTS audio",
            data=format_service_error(exc),
        )
        return JSONResponse(status_code=status.HTTP_502_BAD_GATEWAY, content=payload)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Unexpected TTS error: %s", exc)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Internal server error") from exc

    message = TTSSuccessMessage(status=result.status, result=result.result)
    metadata = TTSMetadata(
        provider=result.metadata["provider"],
        model=result.metadata["model"],
        voice=result.metadata.get("voice"),
        format=result.metadata["format"],
        chunk_count=result.metadata["chunk_count"],
        s3_url=result.metadata.get("s3_url"),
        extra=result.metadata.get("extra"),
    )

    payload = api_ok(
        message=message.model_dump(),
        data=metadata.model_dump(by_alias=True, exclude_none=True),
    )
    return JSONResponse(status_code=status.HTTP_200_OK, content=payload)


@router.post(
    "/stream",
    summary="Stream speech from text",
    response_class=StreamingResponse,
)
async def stream_tts_endpoint(
    request: TTSGenerateRequest,
    service: TTSService = Depends(get_tts_service),
) -> Response:
    """Stream speech audio chunks for long-running TTS jobs."""

    if request.action is TTSAction.BILLING:
        payload = api_error(
            code=status.HTTP_400_BAD_REQUEST,
            message="Billing requests cannot be streamed",
            data={"action": request.action},
        )
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=payload)

    try:
        media_type, iterator, metadata = await service.stream_http(request)
    except ValidationError as exc:
        logger.warning("TTS stream validation error: %s", exc)
        payload = api_error(
            code=status.HTTP_400_BAD_REQUEST,
            message="Invalid TTS request",
            data=format_validation_error(exc),
        )
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=payload)
    except ConfigurationError as exc:
        logger.error("TTS stream configuration error: %s", exc)
        payload = api_error(
            code=status.HTTP_502_BAD_GATEWAY,
            message="TTS configuration error",
            data=format_configuration_error(exc),
        )
        return JSONResponse(status_code=status.HTTP_502_BAD_GATEWAY, content=payload)
    except ProviderError as exc:
        logger.error("TTS stream provider error: %s", exc)
        payload = api_error(
            code=status.HTTP_502_BAD_GATEWAY,
            message="TTS provider error",
            data=format_provider_error(exc),
        )
        return JSONResponse(status_code=status.HTTP_502_BAD_GATEWAY, content=payload)
    except ServiceError as exc:
        logger.error("TTS stream service error: %s", exc)
        payload = api_error(
            code=status.HTTP_502_BAD_GATEWAY,
            message="Failed to stream TTS audio",
            data=format_service_error(exc),
        )
        return JSONResponse(status_code=status.HTTP_502_BAD_GATEWAY, content=payload)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Unexpected TTS stream error: %s", exc)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Internal server error") from exc

    headers = {
        "X-TTS-Provider": metadata.get("provider", ""),
        "X-TTS-Model": metadata.get("model", ""),
    }
    voice = metadata.get("voice")
    if voice:
        headers["X-TTS-Voice"] = voice

    headers = {key: value for key, value in headers.items() if value}
    headers.setdefault("Cache-Control", "no-store")

    return StreamingResponse(iterator, media_type=media_type, headers=headers)


async def _handle_billing_request(request: TTSGenerateRequest, service: TTSService) -> JSONResponse:
    try:
        result = await service.get_billing(request.user_settings)
    except ConfigurationError as exc:
        logger.error("TTS billing configuration error: %s", exc)
        payload = api_error(
            code=status.HTTP_502_BAD_GATEWAY,
            message="TTS billing configuration error",
            data=format_configuration_error(exc),
        )
        return JSONResponse(status_code=status.HTTP_502_BAD_GATEWAY, content=payload)
    except ProviderError as exc:
        logger.error("TTS billing provider error: %s", exc)
        payload = api_error(
            code=status.HTTP_502_BAD_GATEWAY,
            message="TTS billing provider error",
            data=format_provider_error(exc),
        )
        return JSONResponse(status_code=status.HTTP_502_BAD_GATEWAY, content=payload)
    except ServiceError as exc:
        logger.error("TTS billing service error: %s", exc)
        payload = api_error(
            code=status.HTTP_502_BAD_GATEWAY,
            message="Failed to retrieve TTS billing",
            data=format_service_error(exc),
        )
        return JSONResponse(status_code=status.HTTP_502_BAD_GATEWAY, content=payload)

    message = TTSSuccessMessage(status=result.status, result=result.result)
    payload = api_ok(message=message.model_dump(), data=result.result)
    return JSONResponse(status_code=status.HTTP_200_OK, content=payload)


__all__ = ["router"]
