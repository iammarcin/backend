"""Validation helpers for the UFC service layer."""

from __future__ import annotations

from core.exceptions import ValidationError


def normalise_email(email: str) -> str:
    """Return a lowercase email string without surrounding whitespace."""

    return email.strip().lower()


def validate_password(password: str, *, min_length: int) -> str:
    """Ensure ``password`` satisfies the configured minimum length."""

    if len(password) < min_length:
        raise ValidationError(
            f"password must be at least {min_length} characters",
            field="password",
        )
    return password


def validate_page_size(requested: int, *, max_page_size: int) -> int:
    """Ensure pagination requests respect the configured upper bound."""

    if requested > max_page_size:
        raise ValidationError(
            f"page_size cannot exceed {max_page_size}",
            field="page_size",
        )
    return requested


__all__ = [
    "normalise_email",
    "validate_password",
    "validate_page_size",
]
