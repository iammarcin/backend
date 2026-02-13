"""
Helper functions for formatting legacy API responses.
"""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse


def legacy_success_response(result: Any, status_code: int = 200) -> JSONResponse:
    """Format response in legacy API format with snake_case keys.

    Note: The Kotlin mobile app uses @SerializedName("snake_case") annotations,
    so responses MUST use snake_case field names.
    """
    return JSONResponse(
        status_code=status_code,
        content={
            "success": True,
            "code": status_code,
            "message": {
                "status": "completed",
                "result": result
            }
        }
    )


def legacy_error_response(message: str, status_code: int = 500) -> JSONResponse:
    """Format error response in legacy API format."""
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "code": status_code,
            "message": {
                "status": "fail",
                "result": message
            }
        }
    )


__all__ = ["legacy_success_response", "legacy_error_response"]
