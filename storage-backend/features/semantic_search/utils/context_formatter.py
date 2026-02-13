"""Context formatting utilities for semantic search results."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from core.providers.semantic.schemas import SearchResult
from features.semantic_search.utils.token_counter import TokenCounter

logger = logging.getLogger(__name__)


SESSION_CONTEXT_GUIDANCE = (
    "_Use these session summaries to inform your answer. "
    "Only include details relevant to the user's current request._\n"
)


class ContextFormatter:
    """Formats semantic search results into structured context for LLM prompts."""

    def __init__(self, max_tokens: int = 4000) -> None:
        self.max_tokens = max_tokens
        self.token_counter = TokenCounter(max_tokens=max_tokens)

    @staticmethod
    def _format_date(value) -> str:
        if value in (None, "", "None"):
            return "unknown date"
        text = value.isoformat() if hasattr(value, "isoformat") else str(value)
        return text.split("T")[0]

    def format_results(
        self,
        results: list[SearchResult],
        original_query: str,
        include_scores: bool = False,
    ) -> str:
        """Format search results into structured conversational context."""
        if not results:
            return ""

        sessions = self._group_by_session(results)

        context_parts: list[str] = [
            "Based on your previous conversations, here are relevant discussions:\n"
        ]

        for session_id, messages in sessions.items():
            if not messages:
                continue

            metadata = messages[0].metadata
            session_name = metadata.get("session_name", "Untitled Session")
            timestamp = metadata.get("timestamp", "")
            date_str = timestamp.split("T")[0] if timestamp else "unknown date"

            context_parts.append(f"\n## {session_name} ({date_str})\n")

            for result in messages:
                message_type = result.metadata.get("message_type", "unknown")
                # Normalize message_type comparison (handle "User", "user", "AI", "assistant", etc.)
                is_user_message = message_type.lower() in ("user", "human")
                speaker = "**User:**" if is_user_message else "**Assistant:**"
                content = self._truncate_long_message(result.content, max_length=500)

                if include_scores:
                    context_parts.append(
                        f"{speaker} {content} _(score: {result.score:.2f})_\n"
                    )
                else:
                    context_parts.append(f"{speaker} {content}\n")

        full_context = "".join(context_parts)
        full_context += " Use those only if they are relevant for user request!"

        if self.token_counter.count_tokens(full_context) > self.max_tokens:
            logger.warning("Formatted context exceeds token budget, truncating")
            full_context = self.token_counter.truncate_to_budget(full_context)

        return full_context

    def format_session_results(self, *, results: List[Dict[str, object]], original_query: str) -> str:
        """Format session-level search results into markdown context."""

        if not results:
            return ""

        context_parts = ["## Relevant Conversations\n", SESSION_CONTEXT_GUIDANCE]
        for idx, result in enumerate(results, 1):
            summary = result.get("summary", "")
            score = result.get("score", 0.0)
            message_count = result.get("message_count", 0)
            updated_at = self._format_date(result.get("last_updated"))
            header = f"### {idx}. Relevance: {float(score):.2f}"
            if updated_at != "unknown date":
                header += f" — Date: {updated_at}"
            context_parts.append(f"{header}\n**Summary:** {summary}\n")

            topics = ", ".join(result.get("key_topics", []))
            if topics:
                context_parts.append(f"**Topics:** {topics}\n")

            entities = ", ".join(result.get("main_entities", []))
            if entities:
                context_parts.append(f"**Entities:** {entities}\n")

            context_parts.append(f"**Messages:** {message_count}\n")
            context_parts.append("---\n")

        context = "\n".join(context_parts)
        if self.token_counter.count_tokens(context) > self.max_tokens:
            logger.warning("Session context exceeds token budget, truncating")
            context = self.token_counter.truncate_to_budget(context)
        return context

    def format_multi_tier_results(self, *, results: List[Dict[str, Any]], original_query: str) -> str:
        """Format multi-tier hierarchical results."""

        if not results:
            return ""

        context_parts = ["## Relevant Conversations\n", SESSION_CONTEXT_GUIDANCE]
        for idx, result in enumerate(results, 1):
            summary = result.get("session_summary", "")
            topics = ", ".join(result.get("session_topics", []))
            entities = ", ".join(result.get("session_entities", []))
            score = result.get("session_score", 0.0)
            updated_at = self._format_date(result.get("session_last_updated"))
            header = f"### {idx}. Relevance: {float(score):.2f}"
            if updated_at != "unknown date":
                header += f" — Date: {updated_at}"
            context_parts.append(f"{header}\n**Summary:** {summary}\n")
            if topics:
                context_parts.append(f"**Topics:** {topics}\n")
            if entities:
                context_parts.append(f"**Entities:** {entities}\n")

            messages = result.get("matched_messages", [])
            if messages:
                context_parts.append("\n**Key Messages:**\n")
                for msg_idx, message in enumerate(messages, 1):
                    role = "You" if message.get("role") == "user" else "AI"
                    content = (message.get("content") or "")[:300]
                    msg_score = float(message.get("score", 0.0))
                    context_parts.append(
                        f"{msg_idx}. **{role}** (score: {msg_score:.2f}): {content}\n"
                    )
            context_parts.append("\n---\n")

        context = "\n".join(context_parts)
        if self.token_counter.count_tokens(context) > self.max_tokens:
            logger.warning("Multi-tier context exceeds token budget, truncating")
            context = self.token_counter.truncate_to_budget(context)
        return context

    def _group_by_session(
        self, results: list[SearchResult]
    ) -> dict[int, list[SearchResult]]:
        """Group search results by session_id while preserving result order."""
        sessions: dict[int, list[SearchResult]] = {}

        for result in results:
            session_id = result.metadata.get("session_id")
            if session_id is None:
                logger.warning(
                    "Result %s missing session_id metadata", result.message_id
                )
                continue

            sessions.setdefault(session_id, []).append(result)

        return sessions

    def _truncate_long_message(self, content: str, max_length: int = 500) -> str:
        """Truncate individual message content if too long."""
        if len(content) <= max_length:
            return content
        return content[:max_length] + "..."

    def estimate_context_size(self, num_results: int, avg_message_length: int) -> int:
        """Estimate token count before formatting."""
        return self.token_counter.estimate_formatted_context_tokens(
            num_results, avg_message_length
        )


def format_semantic_context(
    results: list[SearchResult],
    original_query: str,
    max_tokens: int = 4000,
    include_scores: bool = False,
) -> str:
    """Convenience function for one-off context formatting."""
    formatter = ContextFormatter(max_tokens=max_tokens)
    return formatter.format_results(results, original_query, include_scores)
