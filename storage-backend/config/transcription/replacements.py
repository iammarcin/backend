from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReplacementRuleConfig:
    """Describe a transcription replacement applied with case-insensitive matching."""

    pattern: str
    replacement: str


_DEFAULT_RULES: tuple[ReplacementRuleConfig, ...] = (
    ReplacementRuleConfig(pattern=r"CLOUD CODE", replacement="Claude Code"),
    ReplacementRuleConfig(pattern=r"CLOUD COWORK", replacement="Claude Cowork"),
    ReplacementRuleConfig(pattern=r"CLOUD COAT", replacement="Claude Code"),
    ReplacementRuleConfig(pattern=r"11 laps", replacement="elevenlabs"),
)


def get_transcription_replacement_configs() -> list[ReplacementRuleConfig]:
    """Return a copy of the default replacement rules."""

    return list(_DEFAULT_RULES)


__all__ = ["ReplacementRuleConfig", "get_transcription_replacement_configs"]
