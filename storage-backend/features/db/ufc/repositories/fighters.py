"""Repositories exposing UFC fighter read and mutation workflows."""

from __future__ import annotations

import logging
from time import perf_counter

from typing import Any, Mapping

from sqlalchemy import and_, false, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import DatabaseError

from ..db_models import Fighter, Subscription
from ..types import FighterRow, FighterWithSubscription
from ..serializers import serialize_fighter, serialize_fighter_with_subscription

logger = logging.getLogger(__name__)


class FighterReadRepository:
    """Expose fighter queries previously implemented in the legacy backend."""

    NON_NULL_CONDITION = and_(
        Fighter.weight_class.is_not(None),
        Fighter.height.is_not(None),
        Fighter.weight.is_not(None),
    )

    SEARCH_COLUMNS = (
        Fighter.name,
        Fighter.tags,
        Fighter.weight_class,
    )

    async def list_fighters(self, session: AsyncSession) -> list[FighterRow]:
        """Return all fighters ordered by identifier."""
        try:
            logger.debug("Repository: list_fighters query starting")
            start = perf_counter()
            result = await session.execute(select(Fighter).order_by(Fighter.id))
            fighters = result.scalars().all()
            duration = perf_counter() - start
            logger.debug(
                "Repository: list_fighters query finished",
                extra={"count": len(fighters), "duration": f"{duration:.2f}s"},
            )
            return [serialize_fighter(fighter) for fighter in fighters]
        except SQLAlchemyError as exc:  # pragma: no cover - defensive guard
            logger.exception("Failed to list fighters from UFC database")
            raise DatabaseError("Unable to list fighters", operation="list_fighters") from exc

    async def list_fighters_with_subscriptions(
        self,
        session: AsyncSession,
        *,
        user_id: int | None = None,
        search: str | None = None,
    ) -> list[FighterWithSubscription]:
        """Return fighters enriched with the caller's subscription status."""
        try:
            logger.debug(
                "Repository: list_fighters_with_subscriptions starting",
                extra={"user_id": user_id, "search": search},
            )
            start = perf_counter()
            join_condition = Fighter.id == Subscription.fighter_id
            if user_id is not None:
                join_condition = and_(join_condition, Subscription.person_id == user_id)
            else:
                join_condition = and_(join_condition, false())

            query = (
                select(Fighter, Subscription)
                .outerjoin(Subscription, join_condition)
                .order_by(Fighter.id)
            )

            filters = [self.NON_NULL_CONDITION]
            if search:
                pattern = f"%{search}%"
                filters.append(self._build_search_clause(pattern))

            if filters:
                query = query.where(and_(*filters))

            result = await session.execute(query)
            rows = result.all()
            duration = perf_counter() - start
            logger.debug(
                "Repository: list_fighters_with_subscriptions completed",
                extra={"rows": len(rows), "duration": f"{duration:.2f}s"},
            )

            fighters: dict[int, FighterWithSubscription] = {}
            for fighter, subscription in rows:
                if fighter.id not in fighters:
                    fighters[fighter.id] = serialize_fighter_with_subscription(
                        fighter,
                        subscribed=subscription is not None,
                    )

            logger.debug(
                "Repository: list_fighters_with_subscriptions serialised",
                extra={"count": len(fighters)},
            )
            return list(fighters.values())
        except SQLAlchemyError as exc:  # pragma: no cover - defensive guard
            logger.exception(
                "Failed to list fighters with subscriptions from UFC database"
            )
            raise DatabaseError(
                "Unable to list fighters with subscription info",
                operation="list_fighters_with_subscriptions",
            ) from exc

    async def search_fighters(
        self, session: AsyncSession, *, search: str
    ) -> list[FighterRow]:
        """Search fighters by partial name, tags, or weight class."""
        try:
            pattern = f"%{search}%"
            logger.debug("Repository: search_fighters starting", extra={"search": search})
            start = perf_counter()
            query = (
                select(Fighter)
                .where(self._build_search_clause(pattern))
                .order_by(Fighter.id)
            )
            result = await session.execute(query)
            fighters = result.scalars().all()
            duration = perf_counter() - start
            logger.debug(
                "Repository: search_fighters finished",
                extra={"count": len(fighters), "duration": f"{duration:.2f}s"},
            )
            return [serialize_fighter(fighter) for fighter in fighters]
        except SQLAlchemyError as exc:  # pragma: no cover - defensive guard
            logger.exception("Failed to search fighters in UFC database")
            raise DatabaseError("Unable to search fighters", operation="search_fighters") from exc

    async def get_fighter_by_name(
        self, session: AsyncSession, *, name: str
    ) -> FighterRow | None:
        """Return the first fighter that matches the supplied name fragment."""
        fighters = await self.search_fighters(session, search=name)
        return fighters[0] if fighters else None

    async def create_fighter(
        self, session: AsyncSession, fighter_data: Mapping[str, Any]
    ) -> tuple[Fighter, bool]:
        """Insert a fighter when unique constraints are satisfied.

        Returns a tuple of the persisted :class:`Fighter` instance and a boolean
        indicating whether a new row was created. When ``False`` the returned
        instance represents the existing duplicate.
        """
        name = str(fighter_data.get("name", "")).strip()
        url = str(fighter_data.get("ufc_url", "")).strip()

        try:
            filters = []
            if name:
                filters.append(Fighter.name == name)
            if url:
                filters.append(Fighter.ufc_url == url)

            duplicate_query = select(Fighter)
            if filters:
                duplicate_query = duplicate_query.where(or_(*filters))

            duplicate_result = await session.execute(duplicate_query)
            existing = duplicate_result.scalars().first()
            if existing is not None:
                logger.info(
                    "Fighter duplicate detected", extra={"fighter_id": existing.id}
                )
                return existing, False

            fighter = Fighter(**fighter_data)
            session.add(fighter)
            await session.flush()
            logger.info("Fighter created", extra={"fighter_id": fighter.id})
            return fighter, True
        except SQLAlchemyError as exc:  # pragma: no cover - defensive guard
            logger.exception("Failed to create fighter")
            raise DatabaseError(
                "Unable to create fighter", operation="create_fighter"
            ) from exc

    async def update_fighter(
        self,
        session: AsyncSession,
        *,
        fighter_id: int,
        updates: Mapping[str, Any],
    ) -> tuple[Fighter | None, bool]:
        """Apply ``updates`` to the fighter identified by ``fighter_id``.

        Returns the updated :class:`Fighter` instance (or ``None`` when the
        fighter is missing) alongside a flag signalling whether any attribute
        changed.
        """
        try:
            result = await session.execute(
                select(Fighter).where(Fighter.id == fighter_id)
            )
            fighter = result.scalars().first()
            if fighter is None:
                logger.info("Fighter not found for update", extra={"fighter_id": fighter_id})
                return None, False

            changed = False
            for key, value in updates.items():
                if not hasattr(fighter, key):
                    continue
                if getattr(fighter, key) == value:
                    continue
                setattr(fighter, key, value)
                changed = True

            if changed:
                await session.flush()
                logger.info(
                    "Fighter updated", extra={"fighter_id": fighter_id, "fields": list(updates.keys())}
                )
            else:
                logger.debug(
                    "No fighter attributes changed", extra={"fighter_id": fighter_id}
                )

            return fighter, changed
        except SQLAlchemyError as exc:  # pragma: no cover - defensive guard
            logger.exception("Failed to update fighter", extra={"fighter_id": fighter_id})
            raise DatabaseError(
                "Unable to update fighter", operation="update_fighter"
            ) from exc

    @classmethod
    def _build_search_clause(cls, pattern: str):
        return or_(*[column.ilike(pattern) for column in cls.SEARCH_COLUMNS])


__all__ = ["FighterReadRepository"]
