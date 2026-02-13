"""Text-only websocket workflow handlers."""

from __future__ import annotations

from typing import Any, Dict, Optional

from features.chat.service import ChatService
from features.chat.utils.prompt_utils import PromptInput
from features.chat.utils.system_prompt import resolve_system_prompt
from core.streaming.manager import StreamingManager


async def handle_text_workflow(
    *,
    prompt: PromptInput,
    settings: Dict[str, Any],
    customer_id: int,
    manager: StreamingManager,
    service: ChatService,
    timings: Dict[str, float],
    user_input: Optional[Dict[str, Any]] = None,
    runtime=None,
) -> Dict[str, Any]:
    """Handle text-only workflow without speech transcription."""

    system_prompt = resolve_system_prompt(settings)

    return await service.stream_response(
        prompt=prompt,
        settings=settings,
        customer_id=customer_id,
        manager=manager,
        system_prompt=system_prompt,
        timings=timings,
        user_input=user_input,
        runtime=runtime,
    )


__all__ = ["handle_text_workflow"]
