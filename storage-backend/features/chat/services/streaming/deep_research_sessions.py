"""Session management helpers for deep research persistence."""

from __future__ import annotations

from typing import Any, Optional

import logging

from features.chat.repositories.chat_sessions import ChatSessionRepository

logger = logging.getLogger(__name__)


async def ensure_session_exists(
    *,
    session_id: Optional[str],
    customer_id: int,
    session_name: str,
    ai_character_name: str,
    db_session: Any,
) -> str:
    """Ensure a session exists for deep research persistence."""

    session_repo = ChatSessionRepository(db_session)

    if session_id:
        existing = await session_repo.get_by_id(
            session_id,
            customer_id=customer_id,
            include_messages=False,
        )
        if existing is not None:
            return session_id

    created = await session_repo.create_session(
        customer_id=customer_id,
        session_name=session_name,
        ai_character_name=ai_character_name,
        tags=["notification"],
    )

    logger.info(
        "Created new deep research session",
        extra={"session_id": created.session_id, "customer_id": customer_id},
    )

    return created.session_id


__all__ = ["ensure_session_exists"]
