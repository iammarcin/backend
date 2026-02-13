"""Utility helpers for coordinating prompt parsing and metadata assembly."""

from __future__ import annotations

import sys
from typing import Any, Dict, List


def get_helper(name: str, fallback: Any) -> Any:
    """Return a helper override when available, otherwise the provided fallback."""

    impl_module = sys.modules.get("features.chat.service_impl")
    if impl_module is not None:
        attribute = getattr(impl_module, name, None)
        if callable(attribute):
            return attribute

        override = getattr(impl_module, "_get_helper", None)
        if callable(override) and override is not get_helper:
            return override(name, fallback)

    service_module = sys.modules.get("features.chat.service")
    if service_module is not None:
        candidate = getattr(service_module, name, None)
        if callable(candidate):
            return candidate
    return fallback


def normalise_event_content(content: Any) -> Dict[str, Any] | List[Any]:
    """Ensure a Claude sidecar event payload can be serialised safely."""

    if isinstance(content, (dict, list)):
        return content
    if content is None:
        return {}
    return {"value": content}


def ensure_dict(content: Any) -> Dict[str, Any]:
    """Coerce arbitrary payloads into a dictionary for persistence."""

    if isinstance(content, dict):
        return dict(content)
    if isinstance(content, list):
        return {"items": list(content)}
    if content is None:
        return {}
    return {"value": content}


def augment_metadata(*, base: Dict[str, Any], extra: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Merge optional metadata dictionaries while preserving existing keys."""

    metadata = dict(base) if base else {}
    if extra:
        metadata.update({key: value for key, value in extra.items() if value is not None})
    return metadata
