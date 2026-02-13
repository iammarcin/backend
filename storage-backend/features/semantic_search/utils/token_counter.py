"""Token counting and budget enforcement for semantic search context."""

from __future__ import annotations

import logging
from typing import Any

try:
    import tiktoken
except ModuleNotFoundError:  # pragma: no cover - optional dependency fallback
    tiktoken = None  # type: ignore[assignment]


class _FallbackEncoding:
    """Minimal stub encoding when tiktoken is unavailable."""

    def encode(self, text: str) -> list[int]:
        return [ord(char) for char in text]

    def decode(self, tokens: list[int]) -> str:
        return "".join(chr(token) for token in tokens)


def _get_fallback_encoding() -> _FallbackEncoding:
    return _FallbackEncoding()

logger = logging.getLogger(__name__)

def _resolve_encoding() -> Any:
    """Resolve the tokenizer encoding, falling back when downloads fail."""

    if tiktoken is None:
        logger.warning("tiktoken unavailable, using fallback encoding")
        return _get_fallback_encoding()

    try:
        # Use cl100k_base encoding (GPT-4, GPT-3.5-turbo, text-embedding-3-*)
        return tiktoken.get_encoding("cl100k_base")
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.warning(
            "tiktoken failed to load encoding, using fallback: %s", exc
        )
        return _get_fallback_encoding()


ENCODING = _resolve_encoding()


class TokenCounter:
    """Counts tokens and enforces budget constraints for context insertion."""

    def __init__(self, max_tokens: int = 4000) -> None:
        """Initialize token counter."""
        self.max_tokens = max_tokens
        self.encoding = ENCODING

    def count_tokens(self, text: str) -> int:
        """Count tokens in a text string."""
        try:
            return len(self.encoding.encode(text))
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.error("Token counting failed: %s", exc, exc_info=True)
            # Fallback: rough estimate (1 token ≈ 4 chars)
            return len(text) // 4

    def truncate_to_budget(self, text: str, max_tokens: int | None = None) -> str:
        """Truncate text to fit within token budget."""
        budget = max_tokens or self.max_tokens
        current_tokens = self.count_tokens(text)

        if current_tokens <= budget:
            return text

        logger.warning(
            "Text exceeds token budget (%s > %s), truncating", current_tokens, budget
        )

        tokens = self.encoding.encode(text)
        truncated_tokens = tokens[:budget]
        truncated_text = self.encoding.decode(truncated_tokens)

        return truncated_text + "... [truncated]"

    def truncate_messages_proportionally(
        self, messages: list[dict[str, Any]], max_tokens: int | None = None
    ) -> list[dict[str, Any]]:
        """Truncate a list of messages to fit within token budget."""
        budget = max_tokens or self.max_tokens
        result: list[dict[str, Any]] = []
        current_tokens = 0

        for message in messages:
            content = message.get("content", "")
            message_tokens = self.count_tokens(content)

            if current_tokens + message_tokens > budget:
                remaining_budget = budget - current_tokens
                if remaining_budget > 50:
                    truncated_content = self.truncate_to_budget(
                        content, remaining_budget
                    )
                    result.append({**message, "content": truncated_content})
                    current_tokens += self.count_tokens(truncated_content)
                break

            result.append(message)
            current_tokens += message_tokens

        logger.info(
            "Truncated %s messages to %s (%s/%s tokens)",
            len(messages),
            len(result),
            current_tokens,
            budget,
        )

        return result

    def estimate_formatted_context_tokens(self, num_messages: int, avg_length: int) -> int:
        """Estimate total tokens for formatted context before building it."""
        base_overhead = 100  # Header text
        per_message_overhead = 20  # "**You:**", "**Assistant:**", etc.

        estimated_content_tokens = (num_messages * avg_length) // 4
        overhead_tokens = (base_overhead + num_messages * per_message_overhead) // 4

        return estimated_content_tokens + overhead_tokens


def count_tokens(text: str) -> int:
    """Convenience function for simple token counting."""
    return TokenCounter().count_tokens(text)
