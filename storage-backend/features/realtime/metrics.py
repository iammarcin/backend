"""Prometheus metrics helpers for realtime websocket sessions."""

from __future__ import annotations

import time
from typing import Optional

try:  # pragma: no cover - optional dependency guard
    from prometheus_client import Counter, Gauge, Histogram  # type: ignore
except Exception:  # pragma: no cover - dependency guard
    Counter = None  # type: ignore
    Gauge = None  # type: ignore
    Histogram = None  # type: ignore


_sessions_active: Optional["Gauge"]
_sessions_total: Optional["Counter"]
_turns_total: Optional["Counter"]
_turn_duration: Optional["Histogram"]
_audio_received: Optional["Counter"]
_audio_sent: Optional["Counter"]
_errors_total: Optional["Counter"]
_provider_events: Optional["Counter"]

if Gauge is None:  # pragma: no cover - dependency guard
    _sessions_active = None
else:  # pragma: no cover - metrics registration
    _sessions_active = Gauge(  # type: ignore[operator]
        "realtime_sessions_active",
        "Number of active realtime sessions",
    )

if Counter is None:  # pragma: no cover - dependency guard
    _sessions_total = None
    _turns_total = None
    _audio_received = None
    _audio_sent = None
    _errors_total = None
    _provider_events = None
else:  # pragma: no cover - metrics registration
    _sessions_total = Counter(  # type: ignore[operator]
        "realtime_sessions_total",
        "Total number of realtime sessions started",
        labelnames=("customer_id",),
    )
    _turns_total = Counter(  # type: ignore[operator]
        "realtime_turns_total",
        "Total number of realtime turns completed",
        labelnames=("session_id", "customer_id"),
    )
    _audio_received = Counter(  # type: ignore[operator]
        "realtime_audio_bytes_received",
        "Total audio bytes received from clients",
        labelnames=("session_id",),
    )
    _audio_sent = Counter(  # type: ignore[operator]
        "realtime_audio_bytes_sent",
        "Total audio bytes sent to clients",
        labelnames=("session_id",),
    )
    _errors_total = Counter(  # type: ignore[operator]
        "realtime_errors_total",
        "Total number of realtime errors emitted",
        labelnames=("error_code", "session_id"),
    )
    _provider_events = Counter(  # type: ignore[operator]
        "realtime_provider_events",
        "Provider events received",
        labelnames=("event_type", "provider"),
    )

if Histogram is None:  # pragma: no cover - dependency guard
    _turn_duration = None
else:  # pragma: no cover - metrics registration
    _turn_duration = Histogram(  # type: ignore[operator]
        "realtime_turn_duration_seconds",
        "Duration of realtime turns",
        buckets=(0.5, 1, 2, 5, 10, 30, 60),
    )


def _inc(counter: Optional["Counter"], *, value: float = 1.0, **labels) -> None:
    """Increment counter if Prometheus client is available."""

    if counter is None:  # pragma: no cover - optional dependency
        return
    if labels:
        counter.labels(**labels).inc(value)
    else:
        counter.inc(value)


def _observe(histogram: Optional["Histogram"], value: float) -> None:
    """Observe histogram value when metric is enabled."""

    if histogram is None:  # pragma: no cover - optional dependency
        return
    histogram.observe(value)


class RealtimeMetricsCollector:
    """Collect realtime metrics for a websocket session."""

    def __init__(self, *, session_id: str, customer_id: int) -> None:
        self.session_id = session_id
        self.customer_id = customer_id
        self.turn_start_time: float | None = None

        _inc(_sessions_total, customer_id=str(customer_id))
        self._update_active_sessions(1)

    def start_turn(self) -> None:
        """Mark start of a provider turn."""

        self.turn_start_time = time.perf_counter()

    def end_turn(self) -> None:
        """Record completed turn metrics."""

        if self.turn_start_time is not None:
            elapsed = max(time.perf_counter() - self.turn_start_time, 0.0)
            _observe(_turn_duration, elapsed)
            self.turn_start_time = None

        _inc(
            _turns_total,
            session_id=self.session_id,
            customer_id=str(self.customer_id),
        )

    def record_audio_received(self, num_bytes: int) -> None:
        """Record audio bytes received from the client."""

        if num_bytes <= 0:
            return
        _inc(
            _audio_received,
            value=float(num_bytes),
            session_id=self.session_id,
        )

    def record_audio_sent(self, num_bytes: int) -> None:
        """Record audio bytes streamed to the client."""

        if num_bytes <= 0:
            return
        _inc(
            _audio_sent,
            value=float(num_bytes),
            session_id=self.session_id,
        )

    def record_error(self, error_code: str) -> None:
        """Record realtime error occurrence."""

        _inc(_errors_total, error_code=error_code, session_id=self.session_id)

    def record_provider_event(self, event_type: str, provider: str) -> None:
        """Record provider event metrics."""

        _inc(_provider_events, event_type=event_type, provider=provider)

    def cleanup(self) -> None:
        """Decrement active session gauge when websocket closes."""

        self._update_active_sessions(-1)

    @staticmethod
    def _update_active_sessions(delta: int) -> None:
        if _sessions_active is None:  # pragma: no cover - optional dependency
            return
        if delta > 0:
            _sessions_active.inc(delta)
        else:
            _sessions_active.dec(-delta)


__all__ = ["RealtimeMetricsCollector"]

