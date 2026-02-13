"""Pydantic schemas for cc4life feature."""

from pydantic import BaseModel, EmailStr


class SubscribeRequest(BaseModel):
    """Request to subscribe to cc4life."""

    email: EmailStr
    source: str = "coming-soon"
    consent: bool = False


class SubscribeResponse(BaseModel):
    """Response for subscribe endpoint."""

    success: bool
    message: str


class ContactRequest(BaseModel):
    """Request to submit a contact form."""

    name: str
    email: EmailStr
    message: str


class ContactResponse(BaseModel):
    """Response for contact endpoint."""

    success: bool
    message: str


__all__ = ["ContactRequest", "ContactResponse", "SubscribeRequest", "SubscribeResponse"]
