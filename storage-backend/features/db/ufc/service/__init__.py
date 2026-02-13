"""Public interface for coordinating UFC database workflows."""

from __future__ import annotations

import logging
from typing import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from core.utils.env import get_env
from infrastructure.aws.queue import SqsQueueService
from ..repositories import (
    AuthRepository,
    FighterReadRepository,
    SubscriptionReadRepository,
    build_repositories,
)
from ..schemas import (
    AuthResult,
    FighterList,
    FighterListParams,
    FighterMutationResult,
    FighterQueueRequest,
    FighterQueueResult,
    FighterSearchParams,
    FighterSubscriptionParams,
    FighterSummary,
    RegistrationResult,
    SubscriptionStatusResponse,
    SubscriptionSummaryList,
    UserExistsResult,
    UserProfile,
)
from ..schemas.requests import (
    AuthLoginRequest,
    AuthRegistrationRequest,
    CreateFighterRequest,
    SubscriptionToggleRequest,
    UpdateFighterRequest,
)
from ..types import UfcRepositories
from .auth import AuthCoordinator
from .fighters import FighterCoordinator
from .queueing import FighterQueueCoordinator
from .subscriptions import SubscriptionCoordinator

logger = logging.getLogger(__name__)


class UfcService:
    """Coordinate UFC domain read and mutation operations across repositories."""

    def __init__(
        self,
        repositories: UfcRepositories | None = None,
        *,
        fighters_repo: FighterReadRepository | None = None,
        subscriptions_repo: SubscriptionReadRepository | None = None,
        auth_repo: AuthRepository | None = None,
        token_provider: Callable[[], str | None] | None = None,
        queue_service: SqsQueueService | None = None,
        max_page_size: int = 2000,
        min_password_length: int = 8,
    ) -> None:
        collection = repositories or build_repositories()
        fighters_repository = fighters_repo or collection.get("fighters") or FighterReadRepository()
        subscriptions_repository = (
            subscriptions_repo or collection.get("subscriptions") or SubscriptionReadRepository()
        )
        auth_repository = auth_repo or collection.get("auth") or AuthRepository()
        token_factory = token_provider or (lambda: get_env("MY_AUTH_BEARER_TOKEN"))

        self._auth = AuthCoordinator(
            auth_repository,
            token_factory,
            min_password_length=min_password_length,
        )
        self._fighters = FighterCoordinator(
            fighters_repository,
            max_page_size=max_page_size,
        )
        self._subscriptions = SubscriptionCoordinator(subscriptions_repository)
        self._queue = FighterQueueCoordinator(queue_service)

        logger.debug(
            "UfcService initialised",
            extra={
                "repositories": list(collection.keys()),
                "max_page_size": max_page_size,
                "min_password_length": min_password_length,
            },
        )

    async def authenticate_user(
        self,
        session: AsyncSession,
        payload: AuthLoginRequest,
    ) -> AuthResult:
        """Authenticate a UFC user and return profile plus token."""

        return await self._auth.authenticate_user(session, payload)

    async def register_user(
        self,
        session: AsyncSession,
        payload: AuthRegistrationRequest,
    ) -> RegistrationResult:
        """Register a new UFC user account."""

        return await self._auth.register_user(session, payload)

    async def user_exists(self, session: AsyncSession, email: str) -> UserExistsResult:
        """Return whether a UFC user exists for ``email``."""

        return await self._auth.user_exists(session, email)

    async def get_user_profile(self, session: AsyncSession, email: str) -> UserProfile:
        """Return the user profile associated with ``email`` or raise if absent."""

        return await self._auth.get_user_profile(session, email)

    async def list_fighters(
        self,
        session: AsyncSession,
        params: FighterListParams | None = None,
    ) -> FighterList:
        """Return a paginated list of fighters."""

        return await self._fighters.list_fighters(session, params)

    async def list_fighters_with_subscriptions(
        self,
        session: AsyncSession,
        params: FighterSubscriptionParams | None = None,
    ) -> FighterList:
        """Return fighters enriched with subscription status for the requesting user."""

        return await self._fighters.list_fighters_with_subscriptions(session, params)

    async def search_fighters(
        self,
        session: AsyncSession,
        params: FighterSearchParams,
    ) -> FighterList:
        """Perform a search across fighter metadata with pagination."""

        return await self._fighters.search_fighters(session, params)

    async def find_fighter_by_id(
        self,
        session: AsyncSession,
        fighter_id: int,
    ) -> FighterSummary | None:
        """Return the fighter that matches ``fighter_id`` or ``None`` when absent."""

        return await self._fighters.find_fighter_by_id(session, fighter_id)

    async def create_fighter(
        self,
        session: AsyncSession,
        payload: CreateFighterRequest,
    ) -> FighterMutationResult:
        """Create a fighter when a duplicate does not already exist."""

        return await self._fighters.create_fighter(session, payload)

    async def update_fighter(
        self,
        session: AsyncSession,
        fighter_id: int,
        payload: UpdateFighterRequest,
    ) -> FighterMutationResult:
        """Update mutable fighter attributes."""

        return await self._fighters.update_fighter(session, fighter_id, payload)

    async def list_subscription_summaries(
        self,
        session: AsyncSession,
    ) -> SubscriptionSummaryList:
        """Return aggregated subscription information for UFC customers."""

        return await self._subscriptions.list_subscription_summaries(session)

    async def toggle_subscription(
        self,
        session: AsyncSession,
        payload: SubscriptionToggleRequest,
    ) -> SubscriptionStatusResponse:
        """Subscribe or unsubscribe a user from a fighter feed."""

        return await self._subscriptions.toggle_subscription(session, payload)

    async def enqueue_fighter_candidate(
        self,
        payload: FighterQueueRequest,
    ) -> FighterQueueResult:
        """Send a fighter candidate payload to the configured SQS queue."""

        return await self._queue.enqueue_candidate(payload)


__all__ = ["UfcService"]
