"""Deprecated models package stub.

The Pydantic schemas previously available under :mod:`core.models` have been moved to
``core.pydantic_schemas`` while provider metadata now resides in
``core.providers.registry``. Importing this package directly is no longer supported and
should be updated to reference the new modules.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "core.models has been deprecated. Use core.pydantic_schemas for FastAPI schemas "
    "and core.providers.registry for provider metadata instead.",
    DeprecationWarning,
    stacklevel=2,
)

raise ImportError(
    "core.models has moved. Import from core.pydantic_schemas or core.providers.registry"
)
