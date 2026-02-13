"""Type definitions for generic tool usage events."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ToolProvider(str, Enum):
    """Supported AI providers for tool usage."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    CLAUDE_CODE = "claude-code"
    XAI = "xai"
    GROQ = "groq"
    DEEPSEEK = "deepseek"
    PERPLEXITY = "perplexity"


class ToolType(str, Enum):
    """Normalized tool types across providers."""

    WEB_SEARCH = "web_search"
    CODE_INTERPRETER = "code_interpreter"
    FUNCTION_CALL = "function_call"
    GOOGLE_SEARCH = "google_search"
    CODE_EXECUTION = "code_execution"
    COMPUTER_USE = "computer_use"
    BASH_EXECUTION = "bash_execution"


class ToolUseEvent(BaseModel):
    """Structured representation of a tool usage event."""

    type: str = Field(default="toolUse", const=True)
    message: str = Field(default="toolUseReceived", const=True)
    provider: ToolProvider
    tool_name: str
    tool_input: Dict[str, Any]
    display_text: str
    call_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        use_enum_values = True


TOOL_EMOJI_MAP: Dict[str, str] = {
    "web_search": "🔍",
    "code_interpreter": "💻",
    "function_call": "🔧",
    "google_search": "🌐",
    "code_execution": "⚡",
    "computer_use": "🖥️",
    "bash_execution": "⚙️",
}

DEFAULT_TOOL_EMOJI = "🛠️"
