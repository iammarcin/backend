"""FastAPI routes for cc4life feature."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.pydantic_schemas import ok as api_ok, error as api_error
from features.cc4life.dependencies import get_cc4life_session
from features.cc4life.schemas import ContactRequest, SubscribeRequest
from features.cc4life.service import CC4LifeService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cc4life", tags=["cc4life"])


def _get_service() -> CC4LifeService:
    """Return a CC4LifeService instance."""
    return CC4LifeService()


@router.post("/subscribe")
async def subscribe(
    request: Request,
    body: SubscribeRequest,
    session: AsyncSession = Depends(get_cc4life_session),
) -> dict:
    """
    Subscribe to cc4life launch notifications.

    Stores email address for launch notification.
    Returns success even if email already exists (privacy protection).
    """
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    service = _get_service()

    try:
        result = await service.subscribe_user(
            session=session,
            email=body.email,
            source=body.source,
            ip_address=ip_address,
            user_agent=user_agent,
            consent=body.consent,
        )
        return api_ok(result.message, data={"success": result.success})
    except Exception as e:
        logger.exception(f"Error subscribing user: {e}")
        return api_error(500, "Internal server error")


@router.post("/contact")
async def contact(
    request: Request,
    body: ContactRequest,
    session: AsyncSession = Depends(get_cc4life_session),
) -> dict:
    """
    Submit a contact form message.

    Stores the message for later review.
    """
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    service = _get_service()

    try:
        result = await service.save_contact(
            session=session,
            name=body.name,
            email=body.email,
            message=body.message,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return api_ok(result.message, data={"success": result.success})
    except Exception as e:
        logger.exception(f"Error saving contact form: {e}")
        return api_error(500, "Internal server error")


__all__ = ["router"]
