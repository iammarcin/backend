from __future__ import annotations

from config.transcription.replacements import ReplacementRuleConfig
from features.audio.transcription_rewrite import TranscriptionRewriteService


def test_transcription_rewrite_service_uses_rules():
    service = TranscriptionRewriteService(
        [ReplacementRuleConfig(pattern=r"foo", replacement="bar")]
    )

    assert service.has_rules is True
    assert service.apply("Foo fighters") == "bar fighters"


def test_transcription_rewrite_service_no_rules_returns_input():
    service = TranscriptionRewriteService([])

    assert service.has_rules is False
    assert service.apply("unchanged") == "unchanged"


def test_transcription_rewrite_service_default_rules():
    service = TranscriptionRewriteService()

    assert service.apply("cloud code and CLOUD COAT") == "Claude Code and Claude Code"
