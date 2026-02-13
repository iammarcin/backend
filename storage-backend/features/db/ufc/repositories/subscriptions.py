"""Repositories for UFC subscription queries and mutations."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import String, func, select

from config.environment import IS_POSTGRESQL
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import DatabaseError

from ..db_models import Fighter, Person, Subscription
from ..types import SubscriptionSummary

logger = logging.getLogger(__name__)


def _group_concat_ids(column):
    """Aggregate IDs into comma-separated string.

    MySQL: GROUP_CONCAT(column)
    PostgreSQL: STRING_AGG(column::text, ',')
    """
    if IS_POSTGRESQL:
        return func.string_agg(column.cast(String), ",")
    return func.group_concat(column)


class SubscriptionReadRepository:
    """Expose subscription aggregations from the legacy UFC provider."""

    async def list_subscription_summaries(
        self, session: AsyncSession
    ) -> list[SubscriptionSummary]:
        """Return user subscription groupings equivalent to the legacy payload."""

        try:
            query = (
                select(
                    Person.account_name,
                    Person.email,
                    _group_concat_ids(Fighter.id).label("subscriptions"),
                )
                .select_from(Person)
                .outerjoin(Subscription, Person.id == Subscription.person_id)
                .outerjoin(Fighter, Subscription.fighter_id == Fighter.id)
                .group_by(Person.id)
                .order_by(Person.id)
            )
            result = await session.execute(query)
            rows = result.all()

            summaries: list[SubscriptionSummary] = []
            for account_name, email, subscription_ids in rows:
                subscriptions = (
                    subscription_ids.split(",") if subscription_ids else []
                )
                summary: SubscriptionSummary = {
                    "accountName": account_name,
                    "email": email,
                    "subscriptions": subscriptions,
                }
                summaries.append(summary)

            return summaries
        except SQLAlchemyError as exc:  # pragma: no cover - defensive guard
            logger.exception("Failed to list UFC subscription summaries")
            raise DatabaseError(
                "Unable to list UFC subscriptions", operation="list_subscription_summaries"
            ) from exc

    async def toggle_subscription(
        self,
        session: AsyncSession,
        *,
        person_id: int,
        fighter_id: int,
        subscribe: bool,
    ) -> tuple[bool, bool, datetime | None]:
        """Subscribe or unsubscribe ``person_id`` from ``fighter_id``.

        Returns a tuple ``(is_subscribed, changed, timestamp)`` where
        ``timestamp`` is populated with the UTC time of the mutation when a
        change occurred.
        """

        try:
            query = select(Subscription).where(
                Subscription.person_id == person_id,
                Subscription.fighter_id == fighter_id,
            )
            result = await session.execute(query)
            existing = result.scalars().first()

            if subscribe:
                if existing is not None:
                    logger.info(
                        "Subscription already exists",
                        extra={"person_id": person_id, "fighter_id": fighter_id},
                    )
                    return True, False, None

                subscription = Subscription(
                    person_id=person_id, fighter_id=fighter_id
                )
                session.add(subscription)
                await session.flush()
                logger.info(
                    "Subscription created",
                    extra={"person_id": person_id, "fighter_id": fighter_id},
                )
                return True, True, datetime.now(timezone.utc)

            if existing is None:
                logger.info(
                    "Subscription already removed",
                    extra={"person_id": person_id, "fighter_id": fighter_id},
                )
                return False, False, None

            await session.delete(existing)
            await session.flush()
            logger.info(
                "Subscription deleted",
                extra={"person_id": person_id, "fighter_id": fighter_id},
            )
            return False, True, datetime.now(timezone.utc)
        except SQLAlchemyError as exc:  # pragma: no cover - defensive guard
            logger.exception(
                "Failed to toggle subscription",
                extra={"person_id": person_id, "fighter_id": fighter_id},
            )
            raise DatabaseError(
                "Unable to manage subscription", operation="toggle_subscription"
            ) from exc


__all__ = ["SubscriptionReadRepository"]
