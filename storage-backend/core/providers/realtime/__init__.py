"""Realtime provider package initialisation."""

from __future__ import annotations

import logging

from .base import BaseRealtimeProvider, RealtimeEvent, RealtimeEventType, TurnStatus
from .factory import (
    get_realtime_provider,
    list_realtime_providers,
    register_realtime_provider,
)
from .utils import NullRealtimeProvider
from .openai import OpenAIRealtimeProvider
from .google import GoogleRealtimeProvider

logger = logging.getLogger(__name__)

register_realtime_provider("null", NullRealtimeProvider)
register_realtime_provider("openai", OpenAIRealtimeProvider)
register_realtime_provider("google", GoogleRealtimeProvider)

logger.info(
    "Initialised realtime providers",
    extra={"providers": list_realtime_providers(include_internal=False)},
)

__all__ = [
    "BaseRealtimeProvider",
    "RealtimeEvent",
    "RealtimeEventType",
    "TurnStatus",
    "get_realtime_provider",
    "list_realtime_providers",
    "register_realtime_provider",
    "NullRealtimeProvider",
    "OpenAIRealtimeProvider",
    "GoogleRealtimeProvider",
]
