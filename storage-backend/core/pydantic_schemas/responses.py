from __future__ import annotations
"""Response models for FastAPI endpoints."""

from typing import Any, Dict, List, Optional

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class APIResponse(BaseModel):
    """Standard API response wrapper."""

    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    code: int = 200


class ChatResponse(BaseModel):
    """Response payload for chat interactions."""

    text: str
    model: str
    provider: str
    reasoning: Optional[str] = None
    citations: Optional[List[Dict[str, Any]]] = None
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    requires_tool_action: Optional[bool] = None


class ImageGenerationResponse(BaseModel):
    """Response payload for image generation."""

    image_url: str
    provider: str
    model: str
    settings: Dict[str, Any]


class VideoGenerationResponse(BaseModel):
    """Response payload for video generation."""

    video_url: str
    provider: str
    model: str
    duration: int
    settings: Dict[str, Any]


__all__ = [
    "APIResponse",
    "ChatResponse",
    "ImageGenerationResponse",
    "VideoGenerationResponse",
]
