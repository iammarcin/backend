"""Indexing operations for the semantic search service."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .base import SemanticSearchBase

logger = logging.getLogger(__name__)


class SemanticSearchIndexingMixin:
    """Provides message indexing CRUD operations."""

    async def index_message(
        self: "SemanticSearchBase",
        message_id: int,
        content: str,
        sender: str,
        customer_id: int,
        session_id: int,
        session_name: str | None = None,
        tags: list[str] | None = None,
        created_at: Any = None,
    ) -> bool:
        """Index a single message."""
        try:
            metadata = self.metadata_builder.build_from_message(
                message_id=message_id,
                content=content,
                sender=sender,
                customer_id=customer_id,
                session_id=session_id,
                session_name=session_name,
                tags=tags,
                created_at=created_at,
            )

            await self.provider.index(
                message_id=message_id,
                content=content,
                metadata=metadata,
            )

            logger.debug(
                "Indexed message %s for customer %s (session %s)",
                message_id,
                customer_id,
                session_id,
            )
            return True
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error(
                "Failed to index message %s: %s", message_id, exc, exc_info=True
            )
            return False

    async def update_message(
        self: "SemanticSearchBase",
        message_id: int,
        content: str,
        sender: str,
        customer_id: int,
        session_id: int,
        session_name: str | None = None,
        tags: list[str] | None = None,
        created_at: Any = None,
    ) -> bool:
        """Update an indexed message."""
        try:
            metadata = self.metadata_builder.build_from_message(
                message_id=message_id,
                content=content,
                sender=sender,
                customer_id=customer_id,
                session_id=session_id,
                session_name=session_name,
                tags=tags,
                created_at=created_at,
            )

            await self.provider.update(
                message_id=message_id,
                content=content,
                metadata=metadata,
            )

            logger.debug("Updated indexed message %s", message_id)
            return True
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error(
                "Failed to update indexed message %s: %s", message_id, exc, exc_info=True
            )
            return False

    async def delete_message(self: "SemanticSearchBase", message_id: int) -> bool:
        """Remove a message from the index."""
        try:
            await self.provider.delete(message_id)
            logger.debug("Deleted indexed message %s", message_id)
            return True
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error(
                "Failed to delete indexed message %s: %s", message_id, exc, exc_info=True
            )
            return False
