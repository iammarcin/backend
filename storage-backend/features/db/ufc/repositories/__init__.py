"""Repository factories for the UFC domain."""

from __future__ import annotations

import logging

from ..types import UfcRepositories

from .auth import AuthRepository
from .fighters import FighterReadRepository
from .subscriptions import SubscriptionReadRepository

logger = logging.getLogger(__name__)


def build_repositories() -> UfcRepositories:
    """Construct repository instances for dependency injection."""

    logger.debug("Building UFC repository collection")
    repositories: UfcRepositories = {
        "fighters": FighterReadRepository(),
        "subscriptions": SubscriptionReadRepository(),
        "auth": AuthRepository(),
    }
    return repositories


__all__ = ["build_repositories"]
