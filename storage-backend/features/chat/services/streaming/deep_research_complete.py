"""Persistence helpers for the full deep research workflow."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import logging

from features.chat.repositories.chat_messages import ChatMessageRepository
from features.chat.repositories.chat_sessions import ChatSessionRepository

logger = logging.getLogger(__name__)


async def save_deep_research_complete_to_db(
    *,
    session_id: str,
    customer_id: int,
    original_query: str,
    optimized_prompt: str,
    research_response: str,
    analysis_response: str,
    citations: List[Dict[str, Any]],
    ai_character_name: str,
    primary_model_name: str,
    db_session: Any,
) -> Dict[str, int]:
    """Persist complete deep research workflow as 4 separate messages."""

    logger.info(
        "Saving complete deep research workflow (4 messages)",
        extra={"session_id": session_id, "customer_id": customer_id},
    )

    message_repo = ChatMessageRepository(db_session)
    session_repo = ChatSessionRepository(db_session)

    user_request_payload = {
        "sender": "User",
        "message": original_query,
    }

    user_message = await message_repo.insert_message(
        session_id=session_id,
        customer_id=customer_id,
        payload=user_request_payload,
        is_ai_message=False,
    )

    optimized_payload = {
        "sender": "System",
        "message": optimized_prompt,
    }

    optimized_message = await message_repo.insert_message(
        session_id=session_id,
        customer_id=customer_id,
        payload=optimized_payload,
        is_ai_message=False,
        claude_code_data={
            "deep_research_stage": "optimization",
            "generated_by_model": primary_model_name,
            "message_type": "deep_research_optimized_prompt",
        },
    )

    citation_metadata: Optional[Dict[str, Any]] = None
    if citations:
        citation_metadata = {
            "deep_research_citations": citations,
            "citations_count": len(citations),
            "deep_research_stage": "research",
        }

    research_payload = {
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

    research_message = await message_repo.insert_message(
        session_id=session_id,
        customer_id=customer_id,
        payload=research_payload,
        is_ai_message=True,
        claude_code_data={
            **(citation_metadata or {}),
            "message_type": "deep_research_raw_results",
        },
    )

    if citation_metadata:
        await message_repo.update_message_metadata(
            message_id=research_message.message_id,
            customer_id=customer_id,
            metadata_updates={"claude_code_data": citation_metadata},
        )

    analysis_payload = {
        "sender": "AI",
        "message": analysis_response,
        "ai_character_name": ai_character_name,
        "api_text_gen_model_name": primary_model_name,
        "api_text_gen_settings": {
            "model": primary_model_name,
            "temperature": 0.7,
            "max_tokens": 4096,
        },
    }

    analysis_message = await message_repo.insert_message(
        session_id=session_id,
        customer_id=customer_id,
        payload=analysis_payload,
        is_ai_message=True,
        claude_code_data={
            "deep_research_stage": "analysis",
            "based_on_research_message_id": research_message.message_id,
            "message_type": "deep_research_analysis",
        },
    )

    await session_repo.add_notification_tag(
        session_id=session_id,
        customer_id=customer_id,
    )

    logger.info(
        "Complete deep research workflow saved (4 messages)",
        extra={
            "session_id": session_id,
            "customer_id": customer_id,
            "user_message_id": user_message.message_id,
            "optimized_prompt_id": optimized_message.message_id,
            "research_message_id": research_message.message_id,
            "analysis_message_id": analysis_message.message_id,
            "citations_count": len(citations),
        },
    )

    return {
        "user_message_id": user_message.message_id,
        "optimized_prompt_id": optimized_message.message_id,
        "research_message_id": research_message.message_id,
        "analysis_message_id": analysis_message.message_id,
    }


__all__ = ["save_deep_research_complete_to_db"]
