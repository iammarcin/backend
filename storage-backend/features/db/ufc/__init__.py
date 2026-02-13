"""UFC domain package scaffolding for upcoming milestones."""

from __future__ import annotations

import logging

from .dependencies import get_ufc_service, get_ufc_session
from .routes import router
from .service import UfcService
from . import repositories, schemas

logger = logging.getLogger(__name__)

__all__ = [
    "router",
    "get_ufc_service",
    "get_ufc_session",
    "UfcService",
    "repositories",
    "schemas",
]
