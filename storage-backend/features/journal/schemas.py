"""Pydantic schemas for journal feature."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class JournalEntry(BaseModel):
    """Single journal entry (sleep or meal)."""

    message_id: int
    entry_type: str = Field(description="'sleep' or 'meals'")
    content: str
    image_urls: list[str] = Field(default_factory=list)
    image_description: Optional[str] = None
    created_at: datetime


class JournalDayData(BaseModel):
    """Combined journal data for a day."""

    date: str = Field(description="Date in YYYY-MM-DD format")
    sleep: Optional[JournalEntry] = Field(None, description="Sleep/day feedback entry")
    meals: Optional[JournalEntry] = Field(None, description="Meals entry with images")


class JournalResponse(BaseModel):
    """Response for journal queries."""

    query_date: str
    today_sleep: Optional[JournalEntry] = None
    yesterday_meals: Optional[JournalEntry] = None
    entries: list[JournalEntry] = Field(default_factory=list)


class ImageDescriptionUpdate(BaseModel):
    """Request to update image description for a message."""

    message_id: int
    image_description: str
