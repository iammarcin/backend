"""Subscription toggle request model."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class SubscriptionToggleRequest(BaseModel):
    """Subscription toggle payload supporting boolean or action inputs."""

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True, extra="forbid")

    person_id: int = Field(..., alias="personId", ge=1)
    fighter_id: int = Field(..., alias="fighterId", ge=1)
    subscribe: bool | None = Field(default=None)
    action: Literal["subscribe", "unsubscribe"] | None = Field(default=None)

    @model_validator(mode="after")
    def _resolve_state(self) -> "SubscriptionToggleRequest":
        if self.subscribe is None and self.action is None:
            raise ValidationError(
                [
                    {
                        "loc": ("subscribe",),
                        "msg": "Either subscribe or action must be provided",
                        "type": "value_error",
                    }
                ]
            )
        if self.subscribe is None and self.action is not None:
            self.subscribe = self.action == "subscribe"
        return self

    def desired_state(self) -> bool:
        assert self.subscribe is not None
        return self.subscribe


__all__ = ["SubscriptionToggleRequest"]
