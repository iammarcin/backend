"""Persistence helper for bug report transcriptions.

Bug reports are saved to a dedicated session with ai_character_name="bugsy",
separate from the user's normal chat flow.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from core.exceptions import ConfigurationError
from features.chat.repositories.chat_messages import ChatMessageRepository
from features.chat.repositories.chat_sessions import ChatSessionRepository
from infrastructure.db.mysql import require_main_session_factory, session_scope

logger = logging.getLogger(__name__)

BUG_REPORT_CHARACTER = "bugsy"
BUG_REPORT_SESSION_NAME = "Bug Reports"


async def persist_bug_report(
    *,
    customer_id: int,
    transcription: str,
) -> Dict[str, Any]:
    """Save a bug report transcription to the dedicated bugsy session.

    Args:
        customer_id: The customer ID submitting the bug report.
        transcription: The transcribed voice message describing the bug.

    Returns:
        Dictionary with session_id and message_id of the saved bug report.
    """
    if not transcription or not transcription.strip():
        logger.warning("Bug report persistence skipped - empty transcription")
        return {"success": False, "error": "empty_transcription"}

    try:
        session_factory = require_main_session_factory()
    except ConfigurationError as exc:
        logger.error("Cannot persist bug report - database not configured: %s", exc)
        return {"success": False, "error": "database_not_configured"}

    async with session_scope(session_factory) as db_session:
        session_repo = ChatSessionRepository(db_session)
        message_repo = ChatMessageRepository(db_session)

        # Get or create the dedicated bugsy session for this customer
        bugsy_session = await session_repo.get_or_create_for_character(
            customer_id=customer_id,
            ai_character_name=BUG_REPORT_CHARACTER,
            session_name=BUG_REPORT_SESSION_NAME,
        )

        # Build the message payload
        message_payload = {
            "message": transcription.strip(),
            "sender": "User",
        }

        # Insert the bug report as a user message
        message = await message_repo.insert_message(
            session_id=bugsy_session.session_id,
            customer_id=customer_id,
            payload=message_payload,
            is_ai_message=False,
        )

        # Update session last_update timestamp
        await session_repo.update_session_metadata(
            session_id=bugsy_session.session_id,
            customer_id=customer_id,
            update_last_mod_time=True,
        )

        logger.info(
            "Bug report saved to bugsy session (customer=%s, session_id=%s, message_id=%s)",
            customer_id,
            bugsy_session.session_id,
            message.message_id,
        )

        return {
            "success": True,
            "session_id": bugsy_session.session_id,
            "message_id": message.message_id,
        }


__all__ = ["persist_bug_report", "BUG_REPORT_CHARACTER", "BUG_REPORT_SESSION_NAME"]
