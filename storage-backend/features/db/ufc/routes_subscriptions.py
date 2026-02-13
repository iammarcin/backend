"""Subscription management endpoint for the UFC feature.

This module keeps the subscription toggle logic isolated from the other route
groups so that changes to dependency injection, logging, or response handling
remain easy to follow.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import DatabaseError, ValidationError
from core.pydantic_schemas import ok as api_ok

from .dependencies import get_ufc_service, get_ufc_session
from .responses import database_error_response, validation_error_response
from .schemas import (
    SubscriptionStatusEnvelope,
    SubscriptionSummaryEnvelope,
    SubscriptionToggleRequest,
    UfcErrorResponse,
)
from .service import UfcService

logger = logging.getLogger(__name__)


def register_subscription_routes(router: APIRouter) -> None:
    """Attach subscription-related endpoints to ``router``."""

    @router.get(
        "/subscriptions/summaries",
        summary="List all user subscriptions",
        response_model=SubscriptionSummaryEnvelope,
        responses={
            status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": UfcErrorResponse},
        },
    )
    async def list_subscription_summaries_endpoint(
        session: AsyncSession = Depends(get_ufc_session),
        service: UfcService = Depends(get_ufc_service),
    ):
        """Return aggregated subscription information for all UFC customers."""

        logger.info("List subscription summaries request")

        try:
            result = await service.list_subscription_summaries(session)
        except DatabaseError as exc:
            return database_error_response(exc)

        data = result.model_dump(mode="json", exclude_none=True)
        meta = {"total": result.total}
        return api_ok(message=f"Retrieved {result.total} subscription summaries", data=data, meta=meta)

    @router.post(
        "/subscriptions/toggle",
        summary="Toggle a fighter subscription",
        response_model=SubscriptionStatusEnvelope,
        responses={
            status.HTTP_400_BAD_REQUEST: {"model": UfcErrorResponse},
            status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": UfcErrorResponse},
        },
    )
    async def toggle_subscription_endpoint(
        payload: SubscriptionToggleRequest,
        session: AsyncSession = Depends(get_ufc_session),
        service: UfcService = Depends(get_ufc_service),
    ):
        """Subscribe or unsubscribe a user from fighter notifications."""

        logger.info(
            "Toggle subscription request",
            extra={"person_id": payload.person_id, "fighter_id": payload.fighter_id},
        )

        try:
            result = await service.toggle_subscription(session, payload)
        except ValidationError as exc:
            return validation_error_response(exc)
        except DatabaseError as exc:
            return database_error_response(exc)

        data = result.model_dump(mode="json", exclude_none=True)
        meta = {"changed": result.changed}
        return api_ok(message=result.message, data=data, meta=meta)


__all__ = ["register_subscription_routes"]

