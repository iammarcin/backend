"""Dependency helpers for the storage feature."""

from __future__ import annotations

from infrastructure.aws.storage import StorageService


def get_storage_service() -> StorageService:
    """Return a lazily instantiated :class:`StorageService`."""

    return StorageService()


__all__ = ["get_storage_service"]
