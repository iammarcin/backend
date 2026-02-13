"""Bulk and health operations for semantic search service."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Iterable

if TYPE_CHECKING:
    from .base import SemanticSearchBase

logger = logging.getLogger(__name__)


class SemanticSearchBulkMixin:
    """Provides bulk delete/index helpers and health checks."""

    async def delete_messages_bulk(
        self: "SemanticSearchBase",
        message_ids: Iterable[int | str | None],
        *,
        concurrency: int = 20,
    ) -> tuple[int, int]:
        """Delete multiple messages concurrently."""

        ids: list[int] = []
        for raw_id in message_ids:
            if raw_id is None:
                continue
            try:
                ids.append(int(raw_id))
            except (TypeError, ValueError):
                logger.warning(
                    "Skipping invalid message id during bulk delete",
                    extra={"id": raw_id},
                )

        unique_ids = list(dict.fromkeys(ids))
        if not unique_ids:
            return 0, 0

        semaphore = asyncio.Semaphore(max(concurrency, 1))
        lock = asyncio.Lock()
        stats = {"success": 0, "failed": 0}

        async def _delete(message_id: int) -> None:
            async with semaphore:
                try:
                    await self.provider.delete(message_id)
                    async with lock:
                        stats["success"] += 1
                except Exception as exc:  # pragma: no cover - defensive logging
                    logger.error(
                        "Failed to delete indexed message %s: %s", message_id, exc, exc_info=True
                    )
                    async with lock:
                        stats["failed"] += 1

        await asyncio.gather(*(_delete(message_id) for message_id in unique_ids))
        return stats["success"], stats["failed"]

    async def bulk_index_messages(
        self: "SemanticSearchBase",
        messages: list[tuple[int, str, dict[str, Any]]],
        batch_size: int = 100,
    ) -> tuple[int, int]:
        """Bulk index multiple messages."""
        try:
            await self.provider.bulk_index(messages, batch_size=batch_size)
            logger.info("Bulk indexed %s messages", len(messages))
            return len(messages), 0
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Bulk indexing failed: %s", exc, exc_info=True)
            return 0, len(messages)

    async def health_check(self: "SemanticSearchBase") -> dict[str, Any]:
        """Check if semantic search is operational."""
        try:
            return await self.provider.health_check()
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Health check failed: %s", exc, exc_info=True)
            return {"healthy": False, "error": str(exc)}
