"""Helpers for semantic indexing tasks triggered by chat history updates."""

from __future__ import annotations

import asyncio
import logging
from typing import Iterable, Tuple

from config.semantic_search import defaults as semantic_defaults
from core.exceptions import ConfigurationError

from features.semantic_search.dependencies import (
    get_semantic_search_service_dependency,
)


logger = logging.getLogger(__name__)


def extract_indexable_content(message) -> str:
    parts: list[str] = []
    text = getattr(message, "message", None)
    if text:
        parts.append(str(text))
    reasoning = getattr(message, "ai_reasoning", None)
    if reasoning:
        parts.append(str(reasoning))
    return "\n\n".join(parts)


async def queue_semantic_indexing_tasks(
    *,
    entries: Iterable[Tuple[str | None, object | None]],
    session_obj,
    customer_id: int,
) -> None:
    if not settings.semantic_search_indexing_enabled:
        return

    valid_entries: list[Tuple[str, object, str]] = []
    for action, message in entries:
        if not message or action not in {"index", "update"}:
            continue
        content = extract_indexable_content(message)
        if not content.strip():
            logger.debug(
                "Skipping semantic indexing for message %s: empty content",
                getattr(message, "message_id", "unknown"),
            )
            continue
        valid_entries.append((action, message, content))

    if not valid_entries:
        return

    try:
        semantic_service = await get_semantic_search_service_dependency()
    except ConfigurationError as exc:
        logger.error(
            "Semantic search misconfigured; cannot queue indexing tasks: %s",
            exc,
            exc_info=True,
        )
        raise

    if not semantic_service:
        logger.debug("Semantic search service unavailable; skipping indexing")
        return

    tags = list(getattr(session_obj, "tags", []) or [])
    session_name = getattr(session_obj, "session_name", None)
    session_id = getattr(session_obj, "session_id", None)

    for action, message, content in valid_entries:
        task_kwargs = dict(
            message_id=getattr(message, "message_id"),
            content=content,
            sender=getattr(message, "sender"),
            customer_id=customer_id,
            session_id=session_id,
            session_name=session_name,
            tags=tags,
            created_at=getattr(message, "created_at", None),
        )

        if action == "update":
            task = semantic_service.update_message(**task_kwargs)
            log_message = "Queued index update for message %s"
        else:
            task = semantic_service.index_message(**task_kwargs)
            log_message = "Queued indexing for message %s"

        asyncio.create_task(task)
        logger.debug(log_message, getattr(message, "message_id", "unknown"))


async def queue_semantic_deletion_tasks(*, message_ids: Iterable[int]) -> None:
    """Queue deletion tasks for removing messages from the semantic index."""

    if not settings.semantic_search_indexing_enabled:
        logger.debug("Semantic indexing disabled; skipping deletion queue")
        return

    ids = [message_id for message_id in message_ids if message_id is not None]
    if not ids:
        return

    try:
        semantic_service = await get_semantic_search_service_dependency()
    except ConfigurationError as exc:
        logger.error(
            "Semantic search misconfigured; cannot queue deletion tasks: %s",
            exc,
            exc_info=True,
        )
        raise

    if not semantic_service:
        logger.debug("Semantic search service unavailable; skipping deletions")
        return

    tasks: list[asyncio.Task[None]] = []

    for message_id in ids:
        task = asyncio.create_task(semantic_service.delete_message(message_id))
        tasks.append(task)
        logger.debug("Queued semantic deletion for message %s", message_id)

    if tasks:
        # Wait for deletions to complete so we don't leak HTTPX clients when the
        # event loop is torn down during tests or shutdown.
        await asyncio.gather(*tasks, return_exceptions=True)


async def delete_session_summary_from_index(
    *, session_id: str, customer_id: int
) -> None:
    """Delete a session summary from the Qdrant index."""

    if not settings.semantic_search_indexing_enabled:
        logger.debug("Semantic indexing disabled; skipping session summary deletion")
        return

    try:
        from features.semantic_search.repositories import SessionSummaryRepository
        from features.semantic_search.services.session_indexing_service import (
            SessionIndexingService,
        )
        from infrastructure.db.mysql import main_session_factory

        if not main_session_factory:
            logger.warning("No database session factory; cannot delete session summary")
            return

        async with main_session_factory() as db:
            summary_repo = SessionSummaryRepository(db)
            indexing_service = SessionIndexingService(summary_repo)
            success = await indexing_service.delete_session(customer_id, session_id)

            if success:
                logger.info("Deleted session summary %s from Qdrant index", session_id)
            else:
                logger.debug(
                    "Session summary %s not found in index or deletion failed",
                    session_id,
                )
    except ConfigurationError as exc:
        logger.warning(
            "Semantic search misconfigured; cannot delete session summary: %s", exc
        )
    except Exception as exc:
        logger.error(
            "Failed to delete session summary %s from index: %s",
            session_id,
            exc,
            exc_info=True,
        )


# Add settings attribute for test compatibility
from core.config import settings as core_settings
settings = core_settings

__all__ = [
    "queue_semantic_indexing_tasks",
    "queue_semantic_deletion_tasks",
    "delete_session_summary_from_index",
    "extract_indexable_content",
    "settings",
]
