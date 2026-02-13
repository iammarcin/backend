"""Repository exports for the Blood feature."""

from __future__ import annotations

from typing import TypedDict, cast

from .tests import BloodTestRepository


class BloodRepositoryCollection(TypedDict, total=False):
    """Typed mapping of Blood repositories available for dependency injection."""

    tests: BloodTestRepository


def build_repositories() -> BloodRepositoryCollection:
    """Instantiate the Blood repositories used by the service layer."""

    return cast(
        BloodRepositoryCollection,
        {
            "tests": BloodTestRepository(),
        },
    )


__all__ = ["BloodRepositoryCollection", "BloodTestRepository", "build_repositories"]
