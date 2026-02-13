"""Chart accumulator for proactive agent streaming sessions.

Stores chart payloads during streaming, to be included in the final message
when stream_end is called. This ensures charts are saved as part of the
main response message instead of as separate messages.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Module-level accumulator: session_id -> list of chart payloads
_chart_accumulator: Dict[str, List[Dict[str, Any]]] = {}


def add_chart(session_id: str, chart_payload: Dict[str, Any]) -> None:
    """Add a chart payload to the accumulator for a session."""
    if session_id not in _chart_accumulator:
        _chart_accumulator[session_id] = []
    _chart_accumulator[session_id].append(chart_payload)
    logger.debug(
        "Added chart to accumulator for session %s (total: %d)",
        session_id[:8],
        len(_chart_accumulator[session_id]),
    )


def get_and_clear_charts(session_id: str) -> List[Dict[str, Any]]:
    """Get accumulated charts for a session and clear the accumulator.

    Returns empty list if no charts accumulated.
    """
    charts = _chart_accumulator.pop(session_id, [])
    if charts:
        logger.debug(
            "Retrieved %d chart(s) from accumulator for session %s",
            len(charts),
            session_id[:8],
        )
    return charts


def clear_charts(session_id: str) -> None:
    """Clear accumulated charts for a session without returning them."""
    if session_id in _chart_accumulator:
        count = len(_chart_accumulator[session_id])
        del _chart_accumulator[session_id]
        logger.debug(
            "Cleared %d chart(s) from accumulator for session %s",
            count,
            session_id[:8],
        )


__all__ = ["add_chart", "get_and_clear_charts", "clear_charts"]
