"""Repository exports for the Garmin domain."""

from __future__ import annotations

from .activity import GarminActivityRepository
from .sleep import GarminSleepRepository
from .summary import GarminSummaryRepository
from .training import GarminTrainingRepository

__all__ = [
    "GarminSleepRepository",
    "GarminSummaryRepository",
    "GarminTrainingRepository",
    "GarminActivityRepository",
    "build_repositories",
]


def build_repositories() -> dict[str, object]:
    """Convenience factory returning instantiated Garmin repositories."""

    return {
        "sleep": GarminSleepRepository(),
        "summary": GarminSummaryRepository(),
        "training": GarminTrainingRepository(),
        "activity": GarminActivityRepository(),
    }
