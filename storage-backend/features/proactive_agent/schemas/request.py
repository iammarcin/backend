"""Request schemas for proactive agent endpoints."""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class MessageSource(str, Enum):
    """Source of the message."""

    TEXT = "text"
    AUDIO_TRANSCRIPTION = "audio_transcription"
    HEARTBEAT = "heartbeat"


class MessageDirection(str, Enum):
    """Direction of message flow."""

    USER_TO_AGENT = "user_to_agent"
    AGENT_TO_USER = "agent_to_user"
    HEARTBEAT = "heartbeat"


class AttachmentType(str, Enum):
    """Type of attachment."""

    IMAGE = "image"
    DOCUMENT = "document"


class Attachment(BaseModel):
    """An attachment (image or document) sent with a message."""

    type: AttachmentType = Field(..., description="Attachment type: image or document")
    url: str = Field(..., description="S3 URL of the uploaded file")
    filename: str = Field(..., description="Original filename")
    mime_type: Optional[str] = Field(
        None,
        description="MIME type (e.g., image/png, application/pdf)",
    )


class SendMessageRequest(BaseModel):
    """Request to send a message to the proactive agent."""

    content: str = Field(..., min_length=1, max_length=30000, description="Message content")
    session_id: Optional[str] = Field(None, description="Session ID (creates new if not provided)")
    source: MessageSource = Field(default=MessageSource.TEXT, description="Message source")
    ai_character_name: str = Field(default="sherlock", description="AI character name (sherlock, bugsy)")
    text_model: Optional[str] = Field(
        None,
        description="LLM model to use (e.g., claude-opus-4-20250514, claude-3-5-haiku-20241022)",
    )
    tts_settings: Optional[dict] = Field(
        None,
        description="TTS configuration: {voice, model, tts_auto_execute}",
    )
    attachments: Optional[List[Attachment]] = Field(
        default=None,
        description="List of image/document attachments (max 5)",
    )

    @field_validator("attachments")
    @classmethod
    def validate_attachments(cls, attachments: Optional[List[Attachment]]) -> Optional[List[Attachment]]:
        if attachments is None:
            return attachments
        if len(attachments) > 5:
            raise ValueError("No more than 5 attachments allowed")
        return attachments

    model_config = {
        "json_schema_extra": {
            "example": {"content": "Hey Sherlock, how are you?", "source": "text", "ai_character_name": "sherlock"}
        }
    }


class AgentNotificationRequest(BaseModel):
    """Request from agent to send a notification (server-to-server)."""

    user_id: int = Field(..., description="Target user ID")
    session_id: str = Field(..., description="Session ID")
    content: str = Field(..., min_length=1, max_length=30000, description="Notification content")
    direction: MessageDirection = Field(
        default=MessageDirection.AGENT_TO_USER, description="Message direction"
    )
    source: MessageSource = Field(default=MessageSource.HEARTBEAT, description="Source of message")
    is_heartbeat_ok: bool = Field(default=False, description="Was this a suppressed HEARTBEAT_OK")
    ai_character_name: str = Field(default="sherlock", description="AI character name (sherlock, bugsy)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": 1,
                "session_id": "abc-123",
                "content": "Disk space at 87%, investigation recommended.",
                "direction": "agent_to_user",
                "source": "heartbeat",
                "ai_character_name": "sherlock",
            }
        }
    }


class ThinkingRequest(BaseModel):
    """Request from agent to send thinking/reasoning content (server-to-server).

    This is sent before the main response to show the agent's thought process.
    """

    user_id: int = Field(..., description="Target user ID")
    session_id: str = Field(..., description="Session ID")
    thinking: str = Field(..., min_length=1, max_length=10000, description="Thinking/reasoning content")
    ai_character_name: str = Field(default="sherlock", description="AI character name")

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": 1,
                "session_id": "abc-123",
                "thinking": "The user is asking about test results. Let me check the recent commits...",
                "ai_character_name": "sherlock",
            }
        }
    }


class StreamingEventType(str, Enum):
    """Type of streaming event from the poller."""

    STREAM_START = "stream_start"  # Streaming has begun
    TEXT_CHUNK = "text_chunk"  # Text content chunk
    THINKING_CHUNK = "thinking_chunk"  # Thinking/reasoning chunk
    STREAM_END = "stream_end"  # Streaming has ended
    TOOL_START = "tool_start"  # Tool execution has begun
    TOOL_RESULT = "tool_result"  # Tool execution completed


class StreamingChunkRequest(BaseModel):
    """Request from agent to send a streaming chunk (server-to-server).

    Used for real-time streaming of Claude's response to the frontend.
    """

    user_id: int = Field(..., description="Target user ID")
    session_id: str = Field(..., description="Session ID")
    event_type: StreamingEventType = Field(..., description="Type of streaming event")
    content: str = Field(default="", max_length=5000, description="Chunk content (empty for start/end)")
    ai_character_name: str = Field(default="sherlock", description="AI character name")
    tts_settings: Optional[dict] = Field(
        None,
        description="TTS configuration passed from stream_start",
    )
    # Accumulated full content for final storage (only set on stream_end)
    full_content: Optional[str] = Field(None, max_length=30000, description="Full accumulated content")
    # Tool execution fields (for tool_start and tool_result events)
    tool_name: Optional[str] = Field(None, max_length=100, description="Name of the tool being executed")
    tool_input: Optional[dict] = Field(None, description="Tool input parameters (JSON)")
    tool_result: Optional[dict] = Field(None, description="Tool execution result (JSON)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": 1,
                "session_id": "abc-123",
                "event_type": "text_chunk",
                "content": "Elementary, my dear",
                "ai_character_name": "sherlock",
            }
        }
    }


__all__ = [
    "SendMessageRequest",
    "AgentNotificationRequest",
    "ThinkingRequest",
    "StreamingEventType",
    "StreamingChunkRequest",
    "MessageSource",
    "MessageDirection",
    "Attachment",
    "AttachmentType",
]
