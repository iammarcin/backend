"""Chat feature package exports and migration scaffolding."""

from __future__ import annotations

__all__ = ["websocket_chat_endpoint", "db_models", "repositories", "schemas"]


def __getattr__(name: str):  # pragma: no cover - compatibility shim
    if name == "websocket_chat_endpoint":
        from features.chat.websocket import websocket_chat_endpoint

        return websocket_chat_endpoint
    if name in {"db_models", "repositories", "schemas"}:
        from importlib import import_module

        return import_module(f"features.chat.{name}")
    raise AttributeError(name)
