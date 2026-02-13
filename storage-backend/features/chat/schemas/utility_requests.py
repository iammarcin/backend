"""Miscellaneous chat request models that support auxiliary endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

from pydantic import AliasChoices, BaseModel, Field

from .base import BaseChatRequest


class AuthRequest(BaseChatRequest):
    """Authenticate a customer for downstream chat interactions."""

    username: str
    password: str


class FavoriteExportRequest(BaseChatRequest):
    """Export favorites, optionally including session metadata."""

    include_session_metadata: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "include_session_metadata", "includeSessionMetadata"
        ),
    )


class FileQueryRequest(BaseChatRequest):
    """Filter chat files using date ranges, name, and extension criteria."""

    older_then_date: Optional[datetime] = Field(
        default=None,
        validation_alias=AliasChoices("older_then_date", "olderThenDate"),
    )
    younger_then_date: Optional[datetime] = Field(
        default=None,
        validation_alias=AliasChoices("younger_then_date", "youngerThenDate"),
    )
    exact_filename: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("exact_filename", "exactFilename"),
    )
    ai_only: bool = Field(
        default=False, validation_alias=AliasChoices("ai_only", "aiOnly")
    )
    offset: int = Field(0, ge=0)
    limit: int = Field(30, ge=0)
    file_extension: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("file_extension", "fileExtension"),
    )
    check_image_locations: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "check_image_locations", "checkImageLocations"
        ),
    )


__all__ = [
    "AuthRequest",
    "FavoriteExportRequest",
    "FileQueryRequest",
]
