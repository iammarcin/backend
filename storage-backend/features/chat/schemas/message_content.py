"""Pydantic models that describe chat message payloads."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class MessageContent(BaseModel):
    """Rich payload describing a chat message and related metadata."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    message_id: Optional[int] = Field(default=None)
    sender: Optional[str] = None
    message: Optional[str] = None
    ai_reasoning: Optional[str] = Field(default=None)
    image_locations: List[str] = Field(default_factory=list)
    chart_data: List[Dict[str, Any]] = Field(default_factory=list)
    file_locations: List[str] = Field(default_factory=list)
    ai_character_name: Optional[str] = Field(default=None)
    api_text_gen_model_name: Optional[str] = Field(default=None)
    api_text_gen_settings: Optional[Dict[str, Any]] = Field(default=None)
    api_tts_gen_model_name: Optional[str] = Field(default=None)
    api_image_gen_settings: Optional[Dict[str, Any]] = Field(default=None)
    image_generation_request: Optional[Dict[str, Any]] = Field(default=None)
    claude_code_data: Optional[Dict[str, Any]] = Field(default=None)
    is_tts: Optional[bool] = Field(default=None)
    is_gps_location_message: Optional[bool] = Field(default=None)
    favorite: Optional[bool] = None
    show_transcribe_button: Optional[bool] = Field(default=None)
    test_mode: Optional[bool] = Field(default=None)

    def to_payload(self, *, include_identifiers: bool = False) -> Dict[str, Any]:
        """Return a dictionary payload with snake_case keys."""

        data = self.model_dump(exclude_none=True)
        if not include_identifiers:
            data.pop("message_id", None)
        return data

    def has_content(self) -> bool:
        """Return True when the payload contains meaningful data."""

        return any(
            [
                self.message,
                self.image_locations,
                self.file_locations,
                self.ai_reasoning,
                self.claude_code_data,
                self.chart_data,
            ]
        )


class MessagePatch(BaseModel):
    """Partial update payload for an existing message."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    message: Optional[str] = None
    ai_reasoning: Optional[str] = Field(default=None)
    image_locations: Optional[List[str]] = Field(default=None)
    file_locations: Optional[List[str]] = Field(default=None)
    chart_data: Optional[List[Dict[str, Any]]] = Field(default=None)
    api_text_gen_model_name: Optional[str] = Field(default=None)
    api_text_gen_settings: Optional[Dict[str, Any]] = Field(default=None)
    api_tts_gen_model_name: Optional[str] = Field(default=None)
    api_image_gen_settings: Optional[Dict[str, Any]] = Field(default=None)
    image_generation_request: Optional[Dict[str, Any]] = Field(default=None)
    claude_code_data: Optional[Dict[str, Any]] = Field(default=None)
    favorite: Optional[bool] = None

    def to_payload(self) -> Dict[str, Any]:
        """Return a serialized dictionary with snake_case keys."""

        return self.model_dump(exclude_none=True)


__all__ = ["MessageContent", "MessagePatch"]
