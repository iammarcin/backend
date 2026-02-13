"""Compatibility layer re-exporting Garmin request schemas."""

from __future__ import annotations

from .activity import ActivityGpsRequest, ActivityRequest
from .base import GarminRequest
from .sleep import SleepIngestRequest
from .wellness import (
    BodyCompositionRequest,
    DailyHealthEventsRequest,
    EnduranceScoreRequest,
    FitnessAgeRequest,
    HRVRequest,
    TrainingReadinessRequest,
    TrainingStatusRequest,
    UserSummaryRequest,
)

__all__ = [
    "ActivityGpsRequest",
    "ActivityRequest",
    "BodyCompositionRequest",
    "DailyHealthEventsRequest",
    "EnduranceScoreRequest",
    "FitnessAgeRequest",
    "HRVRequest",
    "GarminRequest",
    "SleepIngestRequest",
    "TrainingReadinessRequest",
    "TrainingStatusRequest",
    "UserSummaryRequest",
]
