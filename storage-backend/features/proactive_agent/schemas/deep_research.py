"""Deep research request schema for proactive agent."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class DeepResearchRequest(BaseModel):
    """Request from agent to execute deep research (server-to-server).

    Always runs asynchronously:
    - Returns immediately with job_id
    - Research runs in background
    - Result saved to file at /storage/research-results/
    - WebSocket notification on completion

    Triggers a 3-stage workflow:
    1. Prompt optimization
    2. Perplexity research
    3. Conversational analysis with citations
    """

    user_id: int = Field(..., description="Target user ID")
    customer_id: Optional[int] = Field(None, description="Customer ID (defaults to user_id)")
    session_id: str = Field(..., description="Session ID for WebSocket routing")
    ai_character_name: str = Field(default="sherlock", description="AI character name")

    query: str = Field(..., min_length=1, max_length=5000, description="Research question")
    reasoning_effort: Optional[str] = Field(
        default=None,
        description="Reasoning effort level: low/medium/high (defaults to env-based setting)",
    )

    @field_validator("reasoning_effort", mode="before")
    @classmethod
    def validate_reasoning_effort(cls, v: Any) -> Optional[str]:
        if v is None:
            return None  # Will use backend default
        # Support both string and numeric values
        effort_map = {0: "low", 1: "medium", 2: "high", "0": "low", "1": "medium", "2": "high"}
        if isinstance(v, int) and v in effort_map:
            return effort_map[v]
        if isinstance(v, str) and v in effort_map:
            return effort_map[v]
        if isinstance(v, str):
            allowed = {"low", "medium", "high"}
            if v.lower() in allowed:
                return v.lower()
        raise ValueError("reasoning_effort must be low/medium/high or 0/1/2")

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": 1,
                "session_id": "abc-123",
                "ai_character_name": "sherlock",
                "query": "What are the latest developments in quantum computing?",
                "reasoning_effort": "medium",
            }
        },
    }


__all__ = ["DeepResearchRequest"]
