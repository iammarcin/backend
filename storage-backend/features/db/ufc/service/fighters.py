"""Fighter-centric workflows for the UFC service layer."""

from __future__ import annotations

import logging
from time import perf_counter
from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ValidationError
from ..repositories import FighterReadRepository
from ..schemas import (
    FighterList,
    FighterListParams,
    FighterMutationResult,
    FighterSearchParams,
    FighterSubscriptionParams,
    FighterSummary,
)
from ..schemas.requests import CreateFighterRequest, UpdateFighterRequest
from ..types import FighterRow, FighterWithSubscription
from .validators import validate_page_size

logger = logging.getLogger(__name__)


class FighterCoordinator:
    """Handle fighter listing, creation, mutation, and search operations."""

    def __init__(
        self,
        fighters_repo: FighterReadRepository,
        *,
        max_page_size: int,
    ) -> None:
        self._fighters_repo = fighters_repo
        self._max_page_size = max_page_size

    async def list_fighters(
        self,
        session: AsyncSession,
        params: FighterListParams | None = None,
    ) -> FighterList:
        """Return a paginated list of fighters."""

        filters = params or FighterListParams()
        page_size = validate_page_size(filters.page_size, max_page_size=self._max_page_size)
        logger.debug(
            "Service: list_fighters called",
            extra={"params": filters.model_dump(exclude_none=True)},
        )
        start = perf_counter()
        fighters = await self._fetch_fighters(session, search=filters.search)
        duration = perf_counter() - start
        logger.debug(
            "Service: list_fighters repository returned",
            extra={"count": len(fighters), "duration": f"{duration:.2f}s"},
        )
        return self._build_fighter_list(
            fighters,
            page=filters.page,
            page_size=page_size,
            search=filters.search,
            subscriptions_enabled=False,
        )

    async def list_fighters_with_subscriptions(
        self,
        session: AsyncSession,
        params: FighterSubscriptionParams | None = None,
    ) -> FighterList:
        """Return fighters enriched with subscription status for the requesting user."""

        filters = params or FighterSubscriptionParams()
        page_size = validate_page_size(filters.page_size, max_page_size=self._max_page_size)
        logger.debug(
            "Service: list_fighters_with_subscriptions called",
            extra={"params": filters.model_dump(exclude_none=True)},
        )
        start = perf_counter()
        fighters = await self._fighters_repo.list_fighters_with_subscriptions(
            session,
            user_id=filters.user_id,
            search=filters.search,
        )
        duration = perf_counter() - start
        logger.debug(
            "Service: list_fighters_with_subscriptions repository returned",
            extra={"count": len(fighters), "duration": f"{duration:.2f}s"},
        )
        return self._build_fighter_list(
            fighters,
            page=filters.page,
            page_size=page_size,
            search=filters.search,
            subscriptions_enabled=True,
        )

    async def search_fighters(
        self,
        session: AsyncSession,
        params: FighterSearchParams,
    ) -> FighterList:
        """Perform a search across fighter metadata with pagination."""

        page_size = validate_page_size(params.page_size, max_page_size=self._max_page_size)
        logger.debug(
            "Service: search_fighters called",
            extra={"params": params.model_dump(exclude_none=True)},
        )
        start = perf_counter()
        fighters = await self._fighters_repo.search_fighters(session, search=params.search)
        duration = perf_counter() - start
        logger.debug(
            "Service: search_fighters repository returned",
            extra={"count": len(fighters), "duration": f"{duration:.2f}s"},
        )
        return self._build_fighter_list(
            fighters,
            page=params.page,
            page_size=page_size,
            search=params.search,
            subscriptions_enabled=False,
        )

    async def find_fighter_by_id(
        self,
        session: AsyncSession,
        fighter_id: int,
    ) -> FighterSummary | None:
        """Return the fighter that matches ``fighter_id`` or ``None`` when absent."""

        fighters = await self._fighters_repo.list_fighters(session)
        for fighter in fighters:
            if fighter.get("id") == fighter_id:
                logger.debug("Resolved fighter by id", extra={"fighter_id": fighter_id})
                return FighterSummary.model_validate(fighter)

        logger.info("Fighter not found", extra={"fighter_id": fighter_id})
        return None

    async def create_fighter(
        self,
        session: AsyncSession,
        payload: CreateFighterRequest,
    ) -> FighterMutationResult:
        """Create a fighter when a duplicate does not already exist."""

        fighter_data = payload.model_dump(exclude_none=True)
        fighter, created = await self._fighters_repo.create_fighter(session, fighter_data)

        status = "created" if created else "duplicate"
        message = (
            "Fighter created successfully"
            if created
            else "Fighter already exists"
        )

        return FighterMutationResult(
            fighter_id=fighter.id,
            status=status,
            message=message,
            changed=created,
        )

    async def update_fighter(
        self,
        session: AsyncSession,
        fighter_id: int,
        payload: UpdateFighterRequest,
    ) -> FighterMutationResult:
        """Update mutable fighter attributes."""

        updates = payload.to_update_dict()
        # Debug: log sherdog-related fields
        sherdog_fields = {k: v for k, v in updates.items() if 'sherdog' in k.lower() or 'rumour' in k.lower()}
        if sherdog_fields:
            logger.info("Sherdog fields in update", extra={"fighter_id": fighter_id, "sherdog_fields": sherdog_fields})
        logger.debug("Update fields", extra={"fighter_id": fighter_id, "fields": list(updates.keys())})
        if not updates:
            raise ValidationError(
                "At least one field must be provided for update",
                field="body",
            )

        fighter, changed = await self._fighters_repo.update_fighter(
            session,
            fighter_id=fighter_id,
            updates=updates,
        )
        if fighter is None:
            raise ValidationError("Fighter not found", field="fighter_id")

        status = "updated" if changed else "unchanged"
        message = (
            "Fighter updated successfully"
            if changed
            else "No fighter attributes changed"
        )
        return FighterMutationResult(
            fighter_id=fighter.id,
            status=status,
            message=message,
            changed=changed,
        )

    async def _fetch_fighters(
        self,
        session: AsyncSession,
        *,
        search: str | None = None,
    ) -> Sequence[FighterRow]:
        if search:
            logger.debug("Service: _fetch_fighters executing search", extra={"search": search})
            return await self._fighters_repo.search_fighters(session, search=search)
        logger.debug("Service: _fetch_fighters listing all fighters")
        return await self._fighters_repo.list_fighters(session)

    def _build_fighter_list(
        self,
        fighters: Sequence[FighterRow | FighterWithSubscription],
        *,
        page: int,
        page_size: int,
        search: str | None,
        subscriptions_enabled: bool,
    ) -> FighterList:
        total = len(fighters)
        offset = (page - 1) * page_size

        if page > 1 and offset >= total and total > 0:
            raise ValidationError("page exceeds available fighter data", field="page")

        page_rows = list(fighters[offset : offset + page_size])
        items = [FighterSummary.model_validate(row) for row in page_rows]
        has_more = offset + len(page_rows) < total

        return FighterList(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_more=has_more,
            search=search,
            subscriptions_enabled=subscriptions_enabled,
        )


__all__ = ["FighterCoordinator"]
