"""FastAPI dependencies for automation feature."""

from __future__ import annotations

from typing import AsyncGenerator

from features.automation.repositories.automation_repository import AutomationRepository
from infrastructure.db.mysql import require_main_session_factory, session_scope


async def get_automation_repository() -> AsyncGenerator[AutomationRepository, None]:
    """Yield a repository bound to a database session."""
    session_factory = require_main_session_factory()
    async with session_scope(session_factory) as session:
        yield AutomationRepository(session)


__all__ = ["get_automation_repository"]
