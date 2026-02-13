"""Provide qdrant_client stubs when the dependency is missing."""

from __future__ import annotations

import sys
import types


def _stub_class(name: str):
    class _Stub:
        def __init__(self, *args, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    _Stub.__name__ = name
    return _Stub


# Try to import real qdrant_client first - only stub if package is not installed
_qdrant_installed = False
try:
    import qdrant_client as _real_qdrant  # noqa: F401
    _qdrant_installed = True
except ModuleNotFoundError:
    pass

if not _qdrant_installed:
    qdrant_module = types.ModuleType("qdrant_client")

    class AsyncQdrantClient:
        def __init__(self, *args, **kwargs):
            self._args = args
            self._kwargs = kwargs

        async def close(self) -> None:  # pragma: no cover - stub
            return None

        async def upsert(self, *args, **kwargs):
            return None

        async def delete(self, *args, **kwargs):
            return None

    qdrant_module.AsyncQdrantClient = AsyncQdrantClient

    models_module = types.ModuleType("qdrant_client.models")
    for attr in (
        "Distance",
        "FieldCondition",
        "Filter",
        "MatchAny",
        "MatchValue",
        "PayloadSchemaType",
        "PointIdsList",
        "PointStruct",
        "Range",
        "SparseVector",
        "VectorParams",
    ):
        setattr(models_module, attr, _stub_class(attr))

    qdrant_module.models = models_module
    sys.modules["qdrant_client"] = qdrant_module
    sys.modules["qdrant_client.models"] = models_module
