"""Persistence helpers for storing deep research artefacts in existing sessions."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import logging

from features.chat.repositories.chat_messages import ChatMessageRepository
from features.chat.repositories.chat_sessions import ChatSessionRepository

logger = logging.getLogger(__name__)


async def save_deep_research_to_db(
    *,
    session_id: str,
    customer_id: int,
    optimized_prompt: str,
    research_response: str,
    citations: List[Dict[str, Any]],
    ai_character_name: str,
    primary_model_name: str,
    db_session: Any,
) -> Dict[str, int]:
    """Persist optimized prompt and research response as chat messages."""

    logger.info(
        "Saving deep research artefacts",
        extra={"session_id": session_id, "customer_id": customer_id},
    )

    message_repo = ChatMessageRepository(db_session)
    session_repo = ChatSessionRepository(db_session)

    user_payload = {
        "sender": "User",
        "message": optimized_prompt,
    }

    user_message = await message_repo.insert_message(
        session_id=session_id,
        customer_id=customer_id,
        payload=user_payload,
        is_ai_message=False,
    )

    citation_metadata: Optional[Dict[str, Any]] = None
    if citations:
        citation_metadata = {
            "deep_research_citations": citations,
            "citations_count": len(citations),
        }

    ai_payload = {
        "sender": "AI",
        "message": research_response,
        "ai_character_name": ai_character_name,
        "api_text_gen_model_name": "sonar-deep-research",
        "api_text_gen_settings": {
            "model": "sonar-deep-research",
            "temperature": 0.2,
            "max_tokens": 2048,
            "source_model": primary_model_name,
        },
    }

    ai_message = await message_repo.insert_message(
        session_id=session_id,
        customer_id=customer_id,
        payload=ai_payload,
        is_ai_message=True,
        claude_code_data=citation_metadata,
    )

    if citation_metadata:
        await message_repo.update_message_metadata(
            message_id=ai_message.message_id,
            customer_id=customer_id,
            metadata_updates={"claude_code_data": citation_metadata},
        )

    await session_repo.add_notification_tag(
        session_id=session_id,
        customer_id=customer_id,
    )

    logger.info(
        "Deep research artefacts saved",
        extra={
            "session_id": session_id,
            "customer_id": customer_id,
            "user_message_id": user_message.message_id,
            "ai_message_id": ai_message.message_id,
            "citations_count": len(citations),
        },
    )

    return {
        "user_message_id": user_message.message_id,
        "ai_message_id": ai_message.message_id,
    }


__all__ = ["save_deep_research_to_db"]
