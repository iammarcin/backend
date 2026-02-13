from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(slots=True)
class SessionTracker:
    """Track the persisted chat session id for a websocket connection."""

    get_session_id: Callable[[], str | None]
    set_session_id: Callable[[str], None]


__all__ = ["SessionTracker"]
