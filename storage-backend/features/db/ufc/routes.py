"""Top-level UFC routing configuration.

This module exposes the :data:`router` instance consumed by the application
and delegates the concrete endpoint implementations to specialised modules.
Splitting the registration logic keeps individual files focused on a single
responsibility while maintaining the original public import surface.
"""

from __future__ import annotations

from fastapi import APIRouter

from .routes_auth import register_auth_routes
from .routes_fighters import register_fighter_routes
from .routes_subscriptions import register_subscription_routes

router = APIRouter(prefix="/api/v1/ufc", tags=["UFC"])

register_auth_routes(router)
register_fighter_routes(router)
register_subscription_routes(router)

__all__ = ["router"]

