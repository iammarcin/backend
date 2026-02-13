from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Mapping, Sequence

from config.transcription.replacements import (
    ReplacementRuleConfig,
    get_transcription_replacement_configs,
)

logger = logging.getLogger(__name__)

RewriteContext = Mapping[str, object] | None


@dataclass(frozen=True, slots=True)
class _CompiledRule:
    pattern: re.Pattern[str]
    replacement: str

    def apply(self, text: str) -> str:
        return self.pattern.sub(self.replacement, text)


class TranscriptionRewriteService:
    """Apply ordered rewrite rules to transcription text."""

    def __init__(
        self,
        rules: Sequence[ReplacementRuleConfig] | None = None,
    ) -> None:
        configs = list(rules) if rules is not None else get_transcription_replacement_configs()
        self._rules: tuple[_CompiledRule, ...] = tuple(
            _CompiledRule(pattern=re.compile(config.pattern, re.IGNORECASE), replacement=config.replacement)
            for config in configs
        )
        logger.debug("Initialised TranscriptionRewriteService with %s rule(s)", len(self._rules))

    @property
    def has_rules(self) -> bool:
        return bool(self._rules)

    def apply(self, text: str, context: RewriteContext = None) -> str:  # noqa: ARG002 - context reserved for future use
        if not text or not self._rules:
            return text
        result = text
        for rule in self._rules:
            result = rule.apply(result)
        return result


__all__ = ["TranscriptionRewriteService"]
