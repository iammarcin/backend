"""Helper utilities for deep research streaming workflow."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Tuple

from core.streaming.manager import StreamingManager
from features.chat.utils.model_swap import get_provider_for_model


OPTIMIZATION_PROMPT_HEADER = (
    "Please analyze provided chat history and user query. Your task is to "
    "extract the essence of the topic of the conversation and exact user "
    "request from his rough thoughts. Then you need to prepare a detailed "
    "prompt for deep research tool, where it will be directly forwarded "
    "without any additional modifications. It will be like giving a real "
    "researcher a way to dig deep into the topic and give me very detailed "
    "report. it will browse the internet and prepare the final and very "
    "detailed report. So please generate a detailed prompt for this deep "
    "research tool grabbing the essence of user's request in context of the "
    "conversation."
)


ANALYSIS_PROMPT_HEADER = (
    "You are having a friendly conversation with the user. They've asked a "
    "question, and you've just received a formal research report with "
    "information to help answer it. Your job now is to:\n\n"
    "1. Distill the key insights from the research report that are most "
    "relevant to the user's original question\n"
    "2. Explain these insights in a casual, conversational tone as if you're "
    "talking to a friend\n"
    "3. Avoid formal, academic language - make the information approachable "
    "and easy to understand\n"
    "4. Avoid any tables, numbered lists, chapter titles or similar "
    "formatting - just use natural language to explain the report\n"
    "5. Add your own perspective or helpful context where appropriate\n"
    "6. Focus on practical implications or takeaways when relevant"
)


def build_optimization_prompt_text(
    *, user_query: str, chat_history: str, today: str | None = None
) -> str:
    """Compose optimization prompt text with consistent formatting."""

    current_day = today or datetime.now().strftime("%Y-%m-%d")
    return (
        f"Today is {current_day}\n\n"
        f"{OPTIMIZATION_PROMPT_HEADER}\n\n"
        "Return only the prompt for the final tool, without any extra text\n\n"
        f"User request: {user_query}\n\n"
        f"Chat history: {chat_history}"
    )


def build_analysis_prompt_text(
    *,
    original_query: str,
    chat_history: str,
    research_response: str,
    optimized_prompt: str,
    today: str | None = None,
) -> str:
    """Compose analysis stage prompt text."""

    current_day = today or datetime.now().strftime("%Y-%m-%d")
    return (
        f"Today is {current_day}\n\n"
        f"{ANALYSIS_PROMPT_HEADER}\n\n"
        "User's original question:\n"
        f"{original_query}\n\n"
        "Recent conversation context:\n"
        f"{chat_history}\n\n"
        "Research report to analyze (do not share this report directly):\n"
        f"{research_response}\n\n"
        "Research prompt that generated this report:\n"
        f"{optimized_prompt}\n\n"
        "Now, respond to the user's question in a friendly, conversational "
        "way, using the insights from the research."
    )


def extract_user_query(prompt: List[Dict[str, Any]]) -> str:
    """Extract latest user utterance from prompt payload."""

    if not prompt:
        return ""

    user_messages: List[str] = []
    for item in prompt:
        if isinstance(item, dict):
            role = item.get("role")
            if role == "user":
                content = item.get("content")
                extracted = extract_text_from_content(content)
                if extracted:
                    user_messages.append(extracted)
            elif "text" in item and not role:
                text_value = item.get("text")
                if isinstance(text_value, str):
                    user_messages.append(text_value)
        elif isinstance(item, str):
            user_messages.append(item)

    if user_messages:
        return user_messages[-1].strip()

    return str(prompt)


def extract_chat_history(settings: Dict[str, Any]) -> str:
    """Extract and format chat history from settings."""

    history = settings.get("chat_history") if isinstance(settings, dict) else None
    if not history:
        return "No previous conversation context."

    formatted_chunks: List[str] = []
    for entry in history:
        if not isinstance(entry, dict):
            formatted_chunks.append(str(entry))
            continue

        speaker = entry.get("role", "unknown").capitalize()
        content = extract_text_from_content(entry.get("content"))
        formatted = f"{speaker}: {content}".strip()
        if formatted:
            formatted_chunks.append(formatted)

    return "\n".join(formatted_chunks)


def extract_text_from_content(content: Any) -> str:
    """Normalise provider-specific content formats into plain text."""

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: List[str] = []
        for block in content:
            if isinstance(block, dict):
                text_value = block.get("text") or block.get("content")
                if text_value:
                    parts.append(str(text_value))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)

    if isinstance(content, dict):
        text_value = content.get("text") or content.get("content")
        if isinstance(text_value, str):
            return text_value

    return str(content) if content is not None else ""


def resolve_primary_provider(
    settings: Dict[str, Any], customer_id: int, *, logger: Any
) -> Tuple[Any, Dict[str, Any]]:
    """Return provider configured for the user's primary model."""

    text_settings = settings.get("text", {}) if isinstance(settings, dict) else {}
    primary_model = text_settings.get("model")
    if not primary_model:
        primary_model = "gpt-4o-mini"
        logger.warning(
            "No primary model configured, defaulting to %s (customer=%s)",
            primary_model,
            customer_id,
        )

    provider = get_provider_for_model(
        model_name=primary_model,
        base_settings=settings,
        enable_reasoning=text_settings.get("enable_reasoning", False),
    )
    return provider, text_settings


async def emit_deep_research_error(manager: StreamingManager, message: str) -> None:
    """Emit standardised deep research error event."""

    await manager.send_to_queues(
        {
            "type": "custom_event",
            "event_type": "deepResearch",
            "content": {
                "type": "deepResearchError",
                "message": message,
                "stage": "error",
            },
        }
    )


__all__ = [
    "build_optimization_prompt_text",
    "build_analysis_prompt_text",
    "extract_chat_history",
    "extract_user_query",
    "extract_text_from_content",
    "resolve_primary_provider",
    "emit_deep_research_error",
]
