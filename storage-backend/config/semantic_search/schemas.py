"""Pydantic schemas for semantic search configuration files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

SESSION_SUMMARY_CONFIG_PATH = Path("config/semantic_search/session_summary.yaml")


class SummarizationConfig(BaseModel):
    """Model configuration for session summarization."""

    model: str = Field(..., description="LLM used to generate summaries")
    max_tokens: int = Field(..., description="Maximum tokens allocated for the summary output")
    temperature: float = Field(..., description="Sampling temperature for deterministic output")
    prompt_file: str = Field(..., description="Path to the summarization prompt template")
    max_message_characters: int | None = Field(
        default=None,
        description="Maximum number of characters from each message included in the prompt (None = unlimited)",
    )


class BackfillConfig(BaseModel):
    """Backfill execution parameters."""

    min_messages: int = Field(..., description="Minimum number of messages required to summarize a session")
    batch_size: int = Field(..., description="Concurrent summarization limit")
    max_age_days: int = Field(..., description="Skip sessions older than this threshold (0 = disabled)")


class VersioningConfig(BaseModel):
    """Configuration versioning metadata."""

    config_version: int = Field(..., description="Version number for invalidating stale summaries")


class SessionSummaryConfig(BaseModel):
    """Top-level schema for session summarization configuration."""

    summarization: SummarizationConfig
    backfill: BackfillConfig
    versioning: VersioningConfig

    @classmethod
    def load(cls, path: str | Path = SESSION_SUMMARY_CONFIG_PATH) -> "SessionSummaryConfig":
        """Load the configuration from disk."""

        config_path = Path(path)
        if not config_path.exists():
            raise FileNotFoundError(f"Session summary config not found: {config_path}")

        with config_path.open("r", encoding="utf-8") as fh:
            data: dict[str, Any] = yaml.safe_load(fh) or {}

        return cls(**data)


__all__ = [
    "BackfillConfig",
    "SessionSummaryConfig",
    "SummarizationConfig",
    "VersioningConfig",
    "SESSION_SUMMARY_CONFIG_PATH",
]
