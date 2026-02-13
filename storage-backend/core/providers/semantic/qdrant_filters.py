"""Filter builders for Qdrant semantic search provider."""

from __future__ import annotations

from typing import Any

from qdrant_client.models import Range, FieldCondition, Filter, MatchAny, MatchValue

from .schemas import SearchRequest


def build_filter(request: SearchRequest) -> Filter:
    """Build Qdrant filter from search request."""

    must_conditions: list[FieldCondition] = [
        FieldCondition(
            key="customer_id",
            match=MatchValue(value=request.customer_id),
        )
    ]

    if request.tags:
        must_conditions.append(
            FieldCondition(
                key="tags",
                match=MatchAny(any=list(request.tags)),
            )
        )

    if request.session_ids:
        # Normalize session IDs to strings for consistent filtering
        match_values: list[str] = []
        for value in request.session_ids:
            if isinstance(value, int):
                match_values.append(str(value))
            elif isinstance(value, str) and value:
                match_values.append(value)
        if match_values:
            deduplicated = list(dict.fromkeys(match_values))
            must_conditions.append(
                FieldCondition(
                    key="session_id",
                    match=MatchAny(any=deduplicated),
                )
            )

    if request.date_range:
        start, end = request.date_range
        # Only apply date range filter if both start and end are non-empty strings
        if start and end:
            must_conditions.append(
                FieldCondition(
                    key="timestamp",
                    range=Range(
                        gte=start,
                        lte=end,
                    ),
                )
            )

    if request.message_type and request.message_type != "both":
        must_conditions.append(
            FieldCondition(
                key="message_type",
                match=MatchValue(value=request.message_type),
            )
        )

    return Filter(must=must_conditions)


__all__ = ["build_filter"]
