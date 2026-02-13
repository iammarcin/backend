"""
Case conversion utilities for legacy Android app compatibility.

These utilities convert between camelCase (legacy apps) and snake_case (backend).
This is a temporary compatibility layer that should be removed when legacy apps
are decommissioned.
"""

from __future__ import annotations

import re
from typing import Any, Callable


def camel_to_snake(name: str) -> str:
    """
    Convert camelCase to snake_case.

    Examples:
        customerId -> customer_id
        userInput -> user_input
        imageLocations -> image_locations
    """
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def snake_to_camel(name: str) -> str:
    """
    Convert snake_case to camelCase.

    Examples:
        customer_id -> customerId
        user_input -> userInput
        image_locations -> imageLocations
    """
    components = name.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


def deep_convert_keys(obj: Any, converter: Callable[[str], str]) -> Any:
    """
    Recursively convert all dictionary keys using the provided converter function.

    Handles nested dicts and lists of dicts.

    Args:
        obj: The object to convert (dict, list, or scalar)
        converter: Function to convert key names (camel_to_snake or snake_to_camel)

    Returns:
        Object with all dict keys converted
    """
    if isinstance(obj, dict):
        return {converter(k): deep_convert_keys(v, converter) for k, v in obj.items()}
    if isinstance(obj, list):
        return [deep_convert_keys(item, converter) for item in obj]
    return obj


__all__ = ["camel_to_snake", "snake_to_camel", "deep_convert_keys"]
