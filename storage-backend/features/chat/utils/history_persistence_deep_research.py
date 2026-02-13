"""Helpers for persisting deep research workflows from websocket streams."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from fastapi import WebSocket

from core.streaming.manager import StreamingManager
from features.chat.services.streaming.deep_research_persistence import (
    ensure_session_exists,
    save_deep_research_complete_to_db,
    save_deep_research_to_db,
)
from infrastructure.db.mysql import require_main_session_factory, session_scope

from .history_payloads import resolve_prompt_text
from .websocket_session import WorkflowSession
from .websocket_workflow_executor import StandardWorkflowOutcome

logger = logging.getLogger(__name__)


async def persist_complete_deep_research_workflow(
    *,
    websocket: WebSocket,
    session: WorkflowSession,
    customer_id: int,
    user_input: Dict[str, Any],
    settings: Dict[str, Any],
    workflow: StandardWorkflowOutcome,
    manager: StreamingManager,
) -> None:
    """Persist complete deep research workflow as 4 separate messages."""

    research_metadata = workflow.result.get("research_metadata") or {}

    prompt_raw = user_input.get("prompt")
    original_query = resolve_prompt_text(prompt_raw) or ""

    optimized_prompt = research_metadata.get("optimized_prompt", "")
    research_response = research_metadata.get("research_response", "")
    analysis_response = research_metadata.get("analysis_response", "")

    if not original_query or not optimized_prompt or not research_response or not analysis_response:
        logger.warning(
            "Deep research workflow incomplete - missing required components",
            extra={
                "has_original_query": bool(original_query),
                "has_optimized_prompt": bool(optimized_prompt),
                "has_research_response": bool(research_response),
                "has_analysis_response": bool(analysis_response),
            },
        )
        return

    session_id = _resolve_session_id(research_metadata, user_input, session)
    if not session_id:
        logger.error("Cannot persist deep research - no session ID available")
        return

    citations: list[Dict[str, Any]] = []
    result_citations = workflow.result.get("citations")
    if isinstance(result_citations, list):
        citations = list(result_citations)

    text_settings = settings.get("text", {}) if isinstance(settings, dict) else {}
    ai_character_name = text_settings.get("ai_character", "assistant")
    primary_model_name = text_settings.get("model", "gpt-4o-mini")

    session_factory = require_main_session_factory()
    async with session_scope(session_factory) as db_session:
        session_id = await ensure_session_exists(
            session_id=session_id,
            customer_id=customer_id,
            session_name=f"Deep Research: {original_query[:50]}...",
            ai_character_name=ai_character_name,
            db_session=db_session,
        )

        message_ids = await save_deep_research_complete_to_db(
            session_id=session_id,
            customer_id=customer_id,
            original_query=str(original_query),
            optimized_prompt=str(optimized_prompt),
            research_response=str(research_response),
            analysis_response=str(analysis_response),
            citations=citations,
            ai_character_name=str(ai_character_name),
            primary_model_name=str(primary_model_name),
            db_session=db_session,
        )

    if not message_ids:
        return

    result_payload = {
        "session_id": session_id,
        "user_message_id": message_ids.get("user_message_id"),
        "ai_message_id": message_ids.get("analysis_message_id"),
        "optimized_prompt_id": message_ids.get("optimized_prompt_id"),
        "research_message_id": message_ids.get("research_message_id"),
        "analysis_message_id": message_ids.get("analysis_message_id"),
        "deep_research": True,
    }

    logger.info(
        "Persisted deep research workflow for customer %s (session_id=%s, 4 messages)",
        customer_id,
        session_id,
    )

    await manager.send_event(
        {
            "type": "db_operation_executed",
            "content": json.dumps(result_payload),
            "session_id": session.session_id,
        }
    )


async def persist_deep_research_artifacts(
    *,
    websocket: WebSocket,
    session: WorkflowSession,
    customer_id: int,
    settings: Dict[str, Any],
    workflow: StandardWorkflowOutcome,
    session_factory,
    primary_session_id: Optional[str],
) -> None:
    """Persist deep research artefacts into the primary chat session."""

    if not primary_session_id:
        logger.debug("Skipping deep research persistence due to missing session id")
        return

    research_metadata = workflow.result.get("research_metadata") or {}
    optimized_prompt = research_metadata.get("optimized_prompt")
    research_response = research_metadata.get("research_response")

    if not optimized_prompt or not research_response:
        logger.debug("Deep research artefacts incomplete; skipping persistence")
        return

    citations: list[Dict[str, Any]] = []
    result_citations = workflow.result.get("citations")
    if isinstance(result_citations, list):
        citations = list(result_citations)
    else:
        metadata_citations = research_metadata.get("citations")
        if isinstance(metadata_citations, list):
            citations = list(metadata_citations)

    text_settings = settings.get("text", {}) if isinstance(settings, dict) else {}
    ai_character_name = text_settings.get("ai_character", "assistant")
    primary_model_name = text_settings.get("model", "gpt-4o-mini")

    async with session_scope(session_factory) as db_session:
        message_ids = await save_deep_research_to_db(
            session_id=primary_session_id,
            customer_id=customer_id,
            optimized_prompt=str(optimized_prompt),
            research_response=str(research_response),
            citations=citations,
            ai_character_name=str(ai_character_name),
            primary_model_name=str(primary_model_name),
            db_session=db_session,
        )

    if not message_ids:
        return

    if isinstance(research_metadata, dict):
        research_metadata["message_ids"] = message_ids
        research_metadata["notification_tagged"] = True

    payload = {
        "session_id": primary_session_id,
        "user_message_id": message_ids.get("user_message_id"),
        "ai_message_id": message_ids.get("ai_message_id"),
        "is_deep_research_supplement": True,
    }

    await websocket.send_json(
        {
            "type": "db_operation_executed",
            "content": json.dumps(payload),
            "session_id": session.session_id,
        }
    )


def _resolve_session_id(
    research_metadata: Dict[str, Any],
    user_input: Dict[str, Any],
    session: WorkflowSession,
) -> Optional[str]:
    session_id = research_metadata.get("session_id") or None
    if not session_id:
        session_id = user_input.get("session_id") or None
    if not session_id or session_id.strip() == "":
        session_id = session.session_id
    return session_id


__all__ = [
    "persist_complete_deep_research_workflow",
    "persist_deep_research_artifacts",
]
