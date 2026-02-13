"""Circuit breaker for semantic search resilience."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Simple circuit breaker for semantic search provider."""

    def __init__(self, failure_threshold: int = 5, timeout_seconds: int = 60) -> None:
        self.failure_threshold = failure_threshold
        self.timeout = timedelta(seconds=timeout_seconds)
        self.failure_count = 0
        self.last_failure_time: datetime | None = None
        self.state = "CLOSED"  # CLOSED | OPEN | HALF_OPEN

        logger.info(
            "Initialised circuit breaker",
            extra={"failure_threshold": failure_threshold, "timeout_seconds": timeout_seconds},
        )

    def record_success(self) -> None:
        """Reset circuit breaker on successful operation."""
        if self.state != "CLOSED":
            logger.info("Circuit breaker state changed", extra={"from": self.state, "to": "CLOSED"})

        self.failure_count = 0
        self.state = "CLOSED"

    def record_failure(self) -> None:
        """Increment failure count and potentially open circuit."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        if self.failure_count >= self.failure_threshold and self.state == "CLOSED":
            self.state = "OPEN"
            logger.warning(
                "Circuit breaker opened",
                extra={"failure_count": self.failure_count, "threshold": self.failure_threshold},
            )

    def can_attempt(self) -> bool:
        """Check if operation should be attempted."""
        if self.state == "CLOSED":
            return True

        if self.state == "OPEN":
            if self.last_failure_time and datetime.now() - self.last_failure_time > self.timeout:
                self.state = "HALF_OPEN"
                logger.info(
                    "Circuit breaker timeout elapsed",
                    extra={"new_state": self.state},
                )
                return True
            return False

        # HALF_OPEN: allow a single attempt to verify recovery.
        return True


__all__ = ["CircuitBreaker"]
