"""Endpoint for AI-generated session name creation."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Depends, HTTPException

from core.auth import AuthContext, require_auth_context
from core.exceptions import ProviderError, ValidationError
from core.http.errors import format_provider_error, format_validation_error
from core.pydantic_schemas import APIResponse
from features.chat.schemas.session_name_request import SessionNameRequest
from features.chat.service import ChatService
from features.chat.utils.session_name import (
    build_prompt_from_session_history,
    build_session_name_prompt,
    load_session_for_prompt,
    normalize_session_name,
    persist_session_name,
    prepare_session_name_settings,
    request_session_name,
)

from .shared import history_router

logger = logging.getLogger(__name__)


def _prompt_preview(prompt: Any) -> str:
    """Return a short preview of a prompt for logging purposes."""

    if isinstance(prompt, str):
        text = prompt
    else:
        text = " ".join(str(item) for item in prompt) if prompt else ""
    text = (text or "").strip().replace("\n", " ")
    return text[:120] + ("…" if len(text) > 120 else "")


@history_router.post("/session-name", response_model=APIResponse)
async def generate_session_name(
    request: SessionNameRequest,
    auth_context: AuthContext = Depends(require_auth_context),
) -> APIResponse:
    """Generate a session name based on the initial conversation prompt."""

    if auth_context["customer_id"] != request.customer_id:
        raise HTTPException(status_code=403, detail="Access denied: customer ID mismatch")

    service = ChatService()

    logger.info(
        "POST /api/v1/chat/session-name received (customer_id=%s, prompt='%s', session_id=%s, has_settings=%s)",
        request.customer_id,
        _prompt_preview(request.prompt),
        request.session_id,
        request.settings is not None and bool(request.settings),
    )
    logger.debug(
        "Session name request details: customer_id=%s, session_id=%s, prompt_length=%d, settings_keys=%s",
        request.customer_id,
        request.session_id,
        len(request.prompt) if request.prompt else 0,
        list(request.settings.keys()) if isinstance(request.settings, dict) else None,
    )

    session_prompt = request.prompt
    prompt_preview = _prompt_preview(session_prompt)
    session_obj = None

    if request.session_id:
        session_obj = await load_session_for_prompt(
            session_id=request.session_id,
            customer_id=request.customer_id,
            logger=logger,
        )
        if session_obj:
            logger.debug(
                "Loaded session %s with %d messages for name generation",
                request.session_id,
                len(getattr(session_obj, "messages", [])),
            )
        else:
            logger.debug(
                "Session %s not found or has no messages, will use provided prompt",
                request.session_id,
            )

    if (not session_prompt or (isinstance(session_prompt, str) and not session_prompt.strip())) and session_obj:
        session_prompt = build_prompt_from_session_history(session_obj)
        prompt_preview = _prompt_preview(session_prompt)

    if not session_prompt:
        if request.session_id:
            name = normalize_session_name("", prompt_preview)
            logger.info(
                "No prompt or messages available; using fallback name for session %s",
                request.session_id,
            )
            await persist_session_name(
                session_id=request.session_id,
                customer_id=request.customer_id,
                session_name=name,
                logger=logger,
            )
            return APIResponse(
                success=True,
                data={"session_name": name, "session_id": request.session_id},
                code=200,
            )

        raise HTTPException(
            status_code=400,
            detail={"message": "Prompt or existing session content is required"},
        )

    session_prompt = build_session_name_prompt(session_prompt)

    try:
        settings_copy = prepare_session_name_settings(request.settings)
        response = await request_session_name(
            service=service,
            session_prompt=session_prompt,
            settings=settings_copy,
            customer_id=request.customer_id,
        )
    except ValidationError as exc:
        logger.warning("Validation error in /api/v1/chat/session-name: %s", exc)
        raise HTTPException(
            status_code=400,
            detail=format_validation_error(exc),
        ) from exc
    except ProviderError as exc:
        logger.error(
            "Provider error in /api/v1/chat/session-name for customer %s (session=%s): %s",
            request.customer_id,
            request.session_id,
            exc,
        )
        raise HTTPException(
            status_code=502,
            detail=format_provider_error(exc),
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error(
            "Unexpected error in /api/v1/chat/session-name for customer %s (session=%s): %s",
            request.customer_id,
            request.session_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Internal server error") from exc

    name = normalize_session_name(response.text or "", prompt_preview)

    session_id = request.session_id
    if session_id:
        await persist_session_name(
            session_id=session_id,
            customer_id=request.customer_id,
            session_name=name,
            logger=logger,
        )

    logger.info(
        "Session name generated for customer %s -> '%s'", request.customer_id, name
    )
    return APIResponse(
        success=True,
        data={"session_name": name, "session_id": session_id},
        code=200,
    )


__all__ = ["generate_session_name"]
