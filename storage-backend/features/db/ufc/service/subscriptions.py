"""Subscription management helpers for the UFC service layer."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories import SubscriptionReadRepository
from ..schemas import SubscriptionStatusResponse, SubscriptionSummaryItem, SubscriptionSummaryList
from ..schemas.requests import SubscriptionToggleRequest

logger = logging.getLogger(__name__)


class SubscriptionCoordinator:
    """Handle subscription summary retrieval and toggle workflows."""

    def __init__(self, repository: SubscriptionReadRepository) -> None:
        self._repository = repository

    async def list_subscription_summaries(
        self,
        session: AsyncSession,
    ) -> SubscriptionSummaryList:
        """Return aggregated subscription information for UFC customers."""

        summaries = await self._repository.list_subscription_summaries(session)
        items = [SubscriptionSummaryItem.model_validate(summary) for summary in summaries]
        logger.debug("Loaded subscription summaries", extra={"count": len(items)})
        return SubscriptionSummaryList(items=items, total=len(items))

    async def toggle_subscription(
        self,
        session: AsyncSession,
        payload: SubscriptionToggleRequest,
    ) -> SubscriptionStatusResponse:
        """Subscribe or unsubscribe a user from a fighter feed."""

        person_id = payload.person_id
        fighter_id = payload.fighter_id
        subscribe = payload.desired_state()

        subscribed, changed, timestamp = await self._repository.toggle_subscription(
            session,
            person_id=person_id,
            fighter_id=fighter_id,
            subscribe=subscribe,
        )

        status = "1" if subscribed else "0"
        message = (
            "Subscription updated"
            if changed
            else "Subscription already in requested state"
        )

        logger.info(
            "Subscription toggled",
            extra={"person_id": person_id, "fighter_id": fighter_id, "subscribed": subscribed},
        )
        return SubscriptionStatusResponse(
            person_id=person_id,
            fighter_id=fighter_id,
            subscription_status=status,
            updated_at=timestamp,
            message=message,
            changed=changed,
        )


__all__ = ["SubscriptionCoordinator"]
