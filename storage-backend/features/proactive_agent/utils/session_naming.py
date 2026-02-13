"""Session naming utilities for proactive agent.

Triggers AI-generated session naming on first response in production.
Follows Architectural Rule 9: session naming is backend-only, prod-only,
and triggered on first response.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from config.environment import IS_PRODUCTION
from features.proactive_agent.repositories import ProactiveAgentRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Default session names that indicate naming hasn't been triggered
DEFAULT_SESSION_NAMES = {"Sherlock", "Bugsy", "sherlock", "bugsy"}


async def should_trigger_session_naming(
    repository: ProactiveAgentRepository,
    session_id: str,
) -> bool:
    """Check if session naming should be triggered.

    Returns True if:
    1. Running in production
    2. Session exists
    3. Session has default name (just the character name)
    """
    if not IS_PRODUCTION:
        logger.debug("Skipping session naming - not in production")
        return False

    session = await repository.get_session_by_id(session_id)
    if not session:
        logger.warning("Cannot check session naming - session not found: %s", session_id)
        return False

    current_name = session.session_name or ""
    is_default = current_name in DEFAULT_SESSION_NAMES or not current_name.strip()

    if not is_default:
        logger.debug(
            "Session %s already has custom name: '%s'",
            session_id,
            current_name[:50],
        )
        return False

    return True


async def trigger_session_naming_background(
    session_id: str,
    customer_id: int,
) -> None:
    """Trigger session naming in a background task.

    This runs the session naming asynchronously to avoid blocking
    the stream finalization. Errors are logged but don't affect
    the main stream flow.
    """
    try:
        # Import here to avoid circular dependencies
        from features.chat.service import ChatService
        from features.chat.utils.session_name import (
            build_prompt_from_session_history,
            load_session_for_prompt,
            normalize_session_name,
            persist_session_name,
            prepare_session_name_settings,
            request_session_name,
        )

        logger.info(
            "Triggering session naming for session %s (customer %s)",
            session_id,
            customer_id,
        )

        # Load session with messages for prompt generation
        session_obj = await load_session_for_prompt(
            session_id=session_id,
            customer_id=customer_id,
            logger=logger,
        )

        if not session_obj:
            logger.warning(
                "Cannot generate session name - failed to load session %s",
                session_id,
            )
            return

        # Build prompt from session history
        session_prompt = build_prompt_from_session_history(session_obj)
        if not session_prompt:
            logger.debug(
                "No suitable content for session naming in session %s",
                session_id,
            )
            return

        # Generate session name via ChatService
        service = ChatService()
        settings = prepare_session_name_settings(None)

        response = await request_session_name(
            service=service,
            session_prompt=session_prompt,
            settings=settings,
            customer_id=customer_id,
        )

        # Normalize and persist
        prompt_preview = session_prompt[:120] if session_prompt else ""
        name = normalize_session_name(response.text or "", prompt_preview)

        await persist_session_name(
            session_id=session_id,
            customer_id=customer_id,
            session_name=name,
            logger=logger,
        )

        logger.info(
            "Session %s named: '%s'",
            session_id,
            name[:50],
        )

    except Exception as exc:
        # Log but don't propagate - session naming failure shouldn't break streaming
        logger.exception(
            "Failed to generate session name for %s: %s",
            session_id,
            exc,
        )


def schedule_session_naming(session_id: str, customer_id: int) -> None:
    """Schedule session naming as a fire-and-forget background task.

    This is the main entry point - it schedules the naming task
    to run in the background without blocking the caller.
    """
    asyncio.create_task(
        trigger_session_naming_background(session_id, customer_id),
        name=f"session_naming_{session_id}",
    )


__all__ = [
    "should_trigger_session_naming",
    "trigger_session_naming_background",
    "schedule_session_naming",
]
