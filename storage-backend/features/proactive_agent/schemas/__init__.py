"""Pydantic schemas for proactive agent feature.

M4 Cleanup Note: ThinkingRequest, StreamingChunkRequest, and StreamingEventType
are no longer exported as they were only used by the legacy HTTP streaming
endpoints. The schema definitions remain in request.py for reference.

Heartbeat Cleanup Note: HeartbeatInvokeRequest has been removed. Heartbeat
now streams via SDK daemon + WebSocket (same pattern as poller).
"""

from features.proactive_agent.schemas.chart import ChartGenerationRequest
from features.proactive_agent.schemas.deep_research import DeepResearchRequest
from features.proactive_agent.schemas.request import (
    Attachment,
    AttachmentType,
    AgentNotificationRequest,
    MessageDirection,
    MessageSource,
    SendMessageRequest,
)
from features.proactive_agent.schemas.response import (
    MessageListResponse,
    MessageResponse,
    SessionResponse,
)

__all__ = [
    # Request schemas (actively used)
    "SendMessageRequest",
    "AgentNotificationRequest",
    "MessageSource",
    "MessageDirection",
    "Attachment",
    "AttachmentType",
    # Internal schemas (used by event_emitter.py)
    "ChartGenerationRequest",
    "DeepResearchRequest",
    # Response schemas
    "MessageResponse",
    "MessageListResponse",
    "SessionResponse",
]
