"""Session summary generation service."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from pydantic import BaseModel, Field

from config.semantic_search.schemas import (
    SESSION_SUMMARY_CONFIG_PATH,
    SessionSummaryConfig,
)
from core.exceptions import ProviderError, ValidationError
from core.providers.base import BaseTextProvider
from core.providers.factory import get_text_provider
from features.chat.repositories import ChatMessageRepository
from features.semantic_search.repositories import SessionSummaryRepository

logger = logging.getLogger(__name__)


class SummaryOutput(BaseModel):
    """Parsed LLM output."""

    summary: str = Field(..., description="Summarized text of the conversation")
    key_topics: List[str] = Field(default_factory=list)
    main_entities: List[str] = Field(default_factory=list)


class SessionSummaryService:
    """Service responsible for generating and persisting session summaries."""

    def __init__(
        self,
        summary_repo: SessionSummaryRepository,
        message_repo: ChatMessageRepository,
        *,
        config_path: Path | str | None = None,
        provider_overrides: dict[str, Any] | None = None,
        debug_llm: bool = False,
    ) -> None:
        self.summary_repo = summary_repo
        self.message_repo = message_repo
        self.config_path = Path(config_path) if config_path else SESSION_SUMMARY_CONFIG_PATH

        self.config = self._load_config()
        self.prompt_template = self._load_prompt()
        self._text_provider: BaseTextProvider | None = None
        self._provider_overrides = provider_overrides or {}
        self._debug_llm = debug_llm

    def _load_config(self) -> SessionSummaryConfig:
        try:
            return SessionSummaryConfig.load(self.config_path)
        except FileNotFoundError as exc:
            raise ValidationError(str(exc)) from exc

    def _load_prompt(self) -> str:
        prompt_path = Path(self.config.summarization.prompt_file)
        if not prompt_path.exists():
            raise ValidationError(f"Prompt file not found: {prompt_path}")
        return prompt_path.read_text(encoding="utf-8")

    def _format_messages_for_prompt(self, messages: Sequence) -> str:
        max_chars = self.config.summarization.max_message_characters
        formatted: List[str] = []
        for message in messages:
            sender = (message.sender or "user").strip().lower()
            role = "Assistant" if sender in {"ai", "assistant"} else "User"
            content = (message.message or "").strip()
            if not content:
                continue
            if max_chars is not None:
                content = content[:max_chars]
            formatted.append(f"{role}: {content}")
        return "\n\n".join(formatted)

    async def _call_llm_for_summary(self, messages_text: str) -> SummaryOutput:
        prompt = self.prompt_template.format(messages=messages_text)
        summary_text = await self._generate_summary_text(prompt)

        try:
            parsed = self._parse_summary_json(summary_text)
        except (AttributeError, KeyError, json.JSONDecodeError) as exc:
            raise ProviderError(f"Failed to parse LLM response as JSON: {exc}") from exc

        return SummaryOutput(
            summary=parsed["summary"],
            key_topics=parsed.get("key_topics", []),
            main_entities=parsed.get("main_entities", []),
        )

    async def generate_summary_for_session(self, session_id: str, customer_id: int) -> Dict[str, object]:
        """Generate or update a summary for the provided session."""

        messages = list(await self.message_repo.get_messages_for_session(session_id))
        if not messages:
            raise ValidationError(f"No messages found for session {session_id}")

        messages_text = self._format_messages_for_prompt(messages)
        if not messages_text:
            raise ValidationError(f"No summarizable content found for session {session_id}")

        message_count = len(messages)
        min_messages = self.config.backfill.min_messages
        if message_count < min_messages:
            raise ValidationError(
                f"Session {session_id} has {message_count} messages, requires at least {min_messages}",
            )

        summary_output = await self._call_llm_for_summary(messages_text)
        first_message_date = messages[0].created_at
        last_message_date = messages[-1].created_at
        config_version = self.config.versioning.config_version

        existing = await self.summary_repo.get_by_session_id(session_id)
        if existing:
            await self.summary_repo.update(
                session_id=session_id,
                summary=summary_output.summary,
                key_topics=summary_output.key_topics,
                main_entities=summary_output.main_entities,
                message_count=message_count,
                last_message_date=last_message_date,
                summary_model=self.config.summarization.model,
                summary_config_version=config_version,
            )
        else:
            await self.summary_repo.create(
                session_id=session_id,
                customer_id=customer_id,
                summary=summary_output.summary,
                key_topics=summary_output.key_topics,
                main_entities=summary_output.main_entities,
                message_count=message_count,
                first_message_date=first_message_date,
                last_message_date=last_message_date,
                summary_model=self.config.summarization.model,
                summary_config_version=config_version,
            )

        return {
            "session_id": session_id,
            "summary": summary_output.summary,
            "key_topics": summary_output.key_topics,
            "main_entities": summary_output.main_entities,
            "message_count": message_count,
        }

    async def _generate_summary_text(self, prompt: str) -> str:
        provider = self._resolve_text_provider()
        extra_kwargs = self._build_provider_kwargs(provider)
        if self._debug_llm:
            logger.info(
                "LLM prompt payload (chars=%s): %s",
                len(prompt),
                prompt[:20000000],
            )
        response = await provider.generate(
            prompt=prompt,
            temperature=self.config.summarization.temperature,
            max_tokens=self.config.summarization.max_tokens,
            **extra_kwargs,
        )
        if not response.text:
            if self._debug_llm:
                logger.error(
                    "LLM returned empty text (model=%s, provider=%s, metadata=%s)",
                    getattr(response, "model", "unknown"),
                    getattr(response, "provider", "unknown"),
                    getattr(response, "metadata", None),
                )
            raise ProviderError("LLM call failed: empty response")

        if self._debug_llm:
            logger.info("LLM raw response (truncated): %s", response.text[:20000000])

        return response.text

    def _build_provider_kwargs(self, provider: BaseTextProvider) -> dict[str, Any]:
        """Return provider-specific overrides filtered by compatibility."""

        if not self._provider_overrides:
            return {}

        overrides = dict(self._provider_overrides)
        provider_name = getattr(provider, "provider_name", "") or ""
        provider_name = provider_name.lower()

        if provider_name != "gemini":
            overrides.pop("tool_settings", None)
        if provider_name != "openai":
            overrides.pop("builtin_tool_config", None)
        if provider_name != "anthropic":
            overrides.pop("disable_native_tools", None)

        return overrides

    def _resolve_text_provider(self) -> BaseTextProvider:
        if self._text_provider is None:
            settings = {
                "text": {
                    "model": self.config.summarization.model,
                    "temperature": self.config.summarization.temperature,
                    "max_tokens": self.config.summarization.max_tokens,
                }
            }
            self._text_provider = get_text_provider(settings)
            config = self._text_provider.get_model_config()
            if config:
                logger.info(
                    "Session summary provider resolved: provider=%s model=%s",
                    config.provider_name,
                    config.model_name,
                )
        return self._text_provider

    def _parse_summary_json(self, raw_text: str) -> dict[str, object]:
        text = self._strip_code_fences(raw_text)
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            if self._debug_llm:
                logger.error(
                    "LLM summary JSON parse failed: %s | raw=%s",
                    exc,
                    text[:2000],
                )
            extracted = self._extract_json_block(text)
            if extracted is None:
                raise
            logger.info("Extracted JSON block from LLM response before parsing")
            try:
                return json.loads(extracted)
            except json.JSONDecodeError as nested_exc:
                if self._debug_llm:
                    logger.error(
                        "LLM summary JSON parse failed after extraction: %s | raw=%s",
                        nested_exc,
                        extracted[:2000],
                    )
                raise

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        stripped = text.strip()
        if stripped.startswith("```"):
            newline = stripped.find("\n")
            if newline != -1:
                stripped = stripped[newline + 1 :]
            stripped = stripped.rstrip("`").rstrip()
            if stripped.endswith("```"):
                stripped = stripped[: -3].rstrip()
        return stripped

    @staticmethod
    def _extract_json_block(text: str) -> str | None:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        return text[start : end + 1]

    async def get_summary_for_session(self, session_id: str) -> Optional[Dict[str, object]]:
        """Retrieve summary metadata for a session."""

        summary = await self.summary_repo.get_by_session_id(session_id)
        if not summary:
            return None

        return {
            "session_id": summary.session_id,
            "summary": summary.summary,
            "key_topics": summary.key_topics or [],
            "main_entities": summary.main_entities or [],
            "message_count": summary.message_count,
            "generated_at": summary.generated_at.isoformat(),
            "last_updated": summary.last_updated.isoformat(),
            "summary_model": summary.summary_model,
            "summary_config_version": summary.summary_config_version,
        }


__all__ = ["SessionSummaryService", "SummaryOutput"]
