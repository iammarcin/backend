"""Rate limiting utilities for semantic search."""

from __future__ import annotations

import logging
import time
from collections import deque
from typing import Any

from config.semantic_search import defaults as semantic_defaults

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket style rate limiter."""

    def __init__(self, max_requests: int = 60, time_window: float = 60.0) -> None:
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: deque[float] = deque()

    def is_allowed(self, customer_id: int) -> bool:
        """Return True if the request is allowed under the rate limit."""

        now = time.time()

        while self.requests and self.requests[0] < now - self.time_window:
            self.requests.popleft()

        if len(self.requests) >= self.max_requests:
            logger.warning(
                "Rate limit exceeded for customer %s: %s requests in %.1fs",
                customer_id,
                len(self.requests),
                self.time_window,
            )
            return False

        self.requests.append(now)
        return True

    def get_stats(self) -> dict[str, Any]:
        """Expose current limiter statistics."""

        now = time.time()
        recent_requests = sum(1 for ts in self.requests if ts >= now - self.time_window)

        return {
            "recent_requests": recent_requests,
            "max_requests": self.max_requests,
            "time_window": self.time_window,
            "utilization": recent_requests / self.max_requests if self.max_requests else 0.0,
        }


_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """Return singleton rate limiter configured from settings."""

    global _rate_limiter

    if _rate_limiter is None:
        _rate_limiter = RateLimiter(
            max_requests=semantic_defaults.RATE_LIMIT_PER_MINUTE,
            time_window=semantic_defaults.RATE_LIMIT_WINDOW_SECONDS,
        )

    return _rate_limiter


__all__ = ["RateLimiter", "get_rate_limiter"]
