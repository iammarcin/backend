"""Metadata extraction utilities for semantic search."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class MetadataBuilder:
    """Builds metadata dictionaries for semantic search indexing and filtering."""

    @staticmethod
    def build_from_message(
        message_id: int,
        content: str,
        sender: str,
        customer_id: int,
        session_id: int,
        session_name: str | None = None,
        tags: list[str] | None = None,
        created_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Build metadata dictionary from message fields."""
        # Normalize sender to standard message_type values
        # sender can be: "User", "AI", "assistant", or custom character names
        # Normalize to: "user" or "assistant" for consistent filtering
        sender_lower = sender.lower()
        if sender_lower in ("user", "human"):
            normalized_type = "user"
        else:
            # Everything else (AI, assistant, character names) becomes "assistant"
            normalized_type = "assistant"

        metadata: dict[str, Any] = {
            "message_id": message_id,
            "customer_id": customer_id,
            "session_id": session_id,
            "message_type": normalized_type,
            "content_length": len(content),
        }

        if session_name:
            metadata["session_name"] = session_name

        if tags:
            metadata["tags"] = tags

        if created_at:
            if isinstance(created_at, str):
                metadata["timestamp"] = created_at
            else:
                metadata["timestamp"] = created_at.isoformat()

        return metadata

    @staticmethod
    def build_search_filters(
        customer_id: int,
        tags: list[str] | None = None,
        date_range: tuple[str, str] | None = None,
        message_type: str | None = None,
        session_ids: list[str | int] | None = None,
    ) -> dict[str, Any]:
        """Build Qdrant filter conditions from search parameters."""
        must_conditions: list[dict[str, Any]] = [
            {"key": "customer_id", "match": {"value": customer_id}}
        ]

        if message_type:
            must_conditions.append(
                {"key": "message_type", "match": {"value": message_type}}
            )

        if tags:
            must_conditions.append({"key": "tags", "match": {"any": tags}})

        if session_ids:
            must_conditions.append({"key": "session_id", "match": {"any": session_ids}})

        if date_range:
            start_date, end_date = date_range
            must_conditions.append(
                {
                    "key": "timestamp",
                    "range": {
                        "gte": start_date,
                        "lte": end_date,
                    },
                }
            )

        return {"must": must_conditions}

    @staticmethod
    def normalize_tags(tags: list[str] | str | None) -> list[str] | None:
        """Normalize tags input to consistent list format."""
        if not tags:
            return None

        normalized: list[str]
        if isinstance(tags, str):
            normalized = [tag.strip() for tag in tags.split(",") if tag.strip()]
        else:
            normalized = list(tags)

        if not normalized:
            return None

        return sorted({tag.lower() for tag in normalized})
