"""Aggregated UFC request schemas."""

from __future__ import annotations

from .auth import AuthLoginRequest, AuthRegistrationRequest
from .fighters import (
    CreateFighterRequest,
    FighterListParams,
    FighterListQueryParams,
    FighterQueueRequest,
    FighterSearchParams,
    FighterSubscriptionParams,
    UpdateFighterRequest,
)
from .subscriptions import SubscriptionToggleRequest

__all__ = [
    "FighterListParams",
    "FighterSubscriptionParams",
    "FighterListQueryParams",
    "FighterSearchParams",
    "CreateFighterRequest",
    "FighterQueueRequest",
    "UpdateFighterRequest",
    "SubscriptionToggleRequest",
    "AuthLoginRequest",
    "AuthRegistrationRequest",
]
