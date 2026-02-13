"""Chat routes exposing WebSocket and HTTP endpoints."""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from core.auth import AuthContext, require_auth_context
from core.exceptions import ProviderError, ValidationError
from core.http.errors import format_provider_error, format_validation_error
from core.pydantic_schemas import APIResponse, ChatRequest, ChatResponse
from features.chat.service import ChatService
from features.chat.utils.system_prompt import resolve_system_prompt

chat_router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


def _prompt_preview(prompt: Any) -> str:
    """Return a short preview of a prompt for logging purposes."""

    if isinstance(prompt, str):
        text = prompt
    else:
        text = " ".join(str(item) for item in prompt) if prompt else ""
    text = (text or "").strip().replace("\n", " ")
    return text[:120] + ("…" if len(text) > 120 else "")


@chat_router.post("/", response_model=APIResponse)
async def chat_endpoint(
    request: ChatRequest,
    auth_context: AuthContext = Depends(require_auth_context),
) -> APIResponse:
    """HTTP endpoint for non-streaming chat."""

    if auth_context["customer_id"] != request.customer_id:
        raise HTTPException(status_code=403, detail="Access denied: customer ID mismatch")

    service = ChatService()

    logger.info(
        "POST /chat received (customer_id=%s, session_id=%s, prompt='%s')",
        request.customer_id,
        request.session_id,
        _prompt_preview(request.prompt),
    )
    if request.settings:
        logger.debug("POST /chat settings: %s", request.settings)

    try:
        provider_response = await service.generate_response(
            prompt=request.prompt,
            settings=request.settings,
            customer_id=request.customer_id,
            system_prompt=resolve_system_prompt(request.settings),
            user_input=request.model_dump(),
        )
    except ValidationError as exc:
        logger.warning("Validation error in /chat: %s", exc)
        raise HTTPException(
            status_code=400,
            detail=format_validation_error(exc),
        ) from exc
    except ProviderError as exc:
        logger.error("Provider error in /chat: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=format_provider_error(exc),
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Unexpected error in /chat: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error") from exc

    response_data = ChatResponse(
        text=provider_response.text,
        model=provider_response.model,
        provider=provider_response.provider,
        reasoning=provider_response.reasoning,
        citations=provider_response.citations,
        session_id=request.session_id,
        metadata=provider_response.metadata,
        tool_calls=provider_response.tool_calls,
        requires_tool_action=provider_response.requires_tool_action or None,
    )

    logger.info(
        "POST /chat completed (customer_id=%s, model=%s, response_chars=%s)",
        request.customer_id,
        response_data.model,
        len(response_data.text or ""),
    )
    return APIResponse(success=True, data=response_data.model_dump(), code=200)


@chat_router.post("/stream")
async def chat_stream_endpoint(
    request: ChatRequest,
    auth_context: AuthContext = Depends(require_auth_context),
) -> StreamingResponse:
    """HTTP endpoint for streaming chat using Server-Sent Events (SSE)."""

    if auth_context["customer_id"] != request.customer_id:
        raise HTTPException(status_code=403, detail="Access denied: customer ID mismatch")

    service = ChatService()

    logger.info(
        "POST /chat/stream received (customer_id=%s, prompt='%s')",
        request.customer_id,
        _prompt_preview(request.prompt),
    )
    if request.settings:
        logger.debug("POST /chat/stream settings: %s", request.settings)

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for chunk in service.stream_response_chunks(
                prompt=request.prompt,
                settings=request.settings,
                customer_id=request.customer_id,
                system_prompt=resolve_system_prompt(request.settings),
                user_input=request.model_dump(),
            ):
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        except ValidationError as exc:
            logger.warning("Validation error in /chat/stream: %s", exc)
            yield f"data: [ERROR: {format_validation_error(exc)['message']}]\n\n"
        except ProviderError as exc:
            logger.error("Provider error in /chat/stream: %s", exc)
            detail = format_provider_error(exc)
            yield f"data: [ERROR: {detail['message']}]\n\n"
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Unexpected error in /chat/stream: %s", exc, exc_info=True)
            yield "data: [ERROR: Internal server error]\n\n"
        else:
            logger.info(
                "Streaming response completed for customer %s", request.customer_id
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


__all__ = ["chat_router"]
