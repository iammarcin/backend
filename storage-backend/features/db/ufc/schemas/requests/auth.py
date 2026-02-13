"""Authentication payloads for UFC users."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class AuthLoginRequest(BaseModel):
    """Credentials required to authenticate a UFC user."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    email: EmailStr = Field(..., description="Registered email address")
    password: str = Field(
        ..., min_length=8, max_length=128, description="Plain text password supplied by the user"
    )


class AuthRegistrationRequest(BaseModel):
    """Payload used to register a new UFC user."""

    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
        extra="forbid",
    )

    account_name: str = Field(
        ..., alias="accountName", min_length=1, max_length=100, description="Display name"
    )
    email: EmailStr = Field(..., description="Unique email address for the account")
    password: str = Field(
        ..., min_length=8, max_length=128, description="Plain text password supplied by the user"
    )
    lang: str | None = Field(default=None, max_length=5, description="Preferred language code")
    photo: str | None = Field(
        default=None,
        max_length=100,
        description="Optional avatar file name",
    )


__all__ = ["AuthLoginRequest", "AuthRegistrationRequest"]
