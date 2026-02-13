"""Clarification response workflow handler."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict

from core.streaming.manager import StreamingManager
from features.chat.service import ChatService

logger = logging.getLogger(__name__)


def build_enhancement_prompt(
    user_input: str,
    answers: Dict[str, Any] | None = None,
    custom_details: str | None = None,
    auto_enhance: bool = False,
) -> str:
    """Build prompt for LLM to enhance user's concept."""

    if auto_enhance:
        # Auto-enhancement without answers
        return f"""You are an expert prompt engineer specializing in AI video and image generation.

The user provided this concept:
"{user_input}"

They chose to auto-enhance without answering clarifying questions. Your task is to:
1. Interpret their concept creatively
2. Make sensible assumptions about mood, setting, lighting, and style
3. Create a detailed, visually-rich prompt (2-4 sentences) optimized for AI generators
4. Choose one coherent aesthetic direction (don't try to include every possible interpretation)

Write ONLY the enhanced prompt, no preamble or explanation.

Guidelines:
- Default to cinematic, visually striking aesthetics
- Include specific lighting (golden hour, volumetric, neon, etc.)
- Specify camera movement if relevant (dolly, pan, orbit)
- Add atmosphere/mood descriptors
- Use concrete visual terms

Your enhanced prompt:"""

    # Enhancement with user answers
    answers_text = ""
    if answers:
        answers_text = "\n".join([f"- {key}: {value}" for key, value in answers.items()])

    return f"""You are an expert prompt engineer specializing in AI video and image generation.

The user's initial concept:
"{user_input}"

They answered these clarification questions:
{answers_text}

Additional details from user:
"{custom_details or 'None'}"

Your task is to create a single, detailed, visually-rich prompt (2-4 sentences) that:
1. Incorporates all the information provided
2. Uses vivid, descriptive language that AI generators understand
3. Specifies lighting, colors, atmosphere, and composition
4. Avoids vague terms like "beautiful" or "amazing"
5. Focuses on visual elements that can be rendered

Write ONLY the enhanced prompt, no preamble or explanation. Start directly with the description.

Examples of good enhanced prompts:
- "A serene mountain landscape at golden hour, with soft orange and pink light illuminating snow-capped peaks. Gentle mist rolls through a pine valley below. Cinematic wide shot with slow forward camera movement."
- "A neon-lit cyberpunk city street at night, rain-slicked pavement reflecting vibrant purple and blue signs. Crowds of people with umbrellas move through the frame. Low-angle tracking shot following a hooded figure."
- "An ancient library filled with towering bookshelves reaching into darkness above. Warm candlelight flickers across weathered leather spines. Dust particles drift through shafts of light from high windows. Slow orbiting camera movement."

Your enhanced prompt:"""


async def handle_clarification_workflow(
    *,
    user_input: str,
    answers: Dict[str, Any] | None,
    custom_details: str | None,
    auto_enhance: bool,
    auto_generate_images: bool,
    settings: Dict[str, Any],
    customer_id: int,
    manager: StreamingManager,
    service: ChatService,
    timings: Dict[str, float],
    completion_token: str | None = None,
) -> Dict[str, Any]:
    """Handle clarification response and prompt enhancement workflow.

    Args:
        completion_token: Optional completion ownership token. Clarification
            workflows currently do **not** take ownership of completion; the
            caller (`run_clarification_workflow`) retains the token and is
            responsible for closing the stream. The parameter exists for
            consistency with other workflows and to make ownership explicit in
            the signature.
    """

    logger.info(
        "Starting clarification workflow (customer=%s, auto_enhance=%s, auto_images=%s)",
        customer_id,
        auto_enhance,
        auto_generate_images,
    )

    # Build enhancement system prompt
    enhancement_prompt = build_enhancement_prompt(
        user_input=user_input,
        answers=answers,
        custom_details=custom_details,
        auto_enhance=auto_enhance,
    )

    logger.debug(
        "Enhancement prompt built (customer=%s, chars=%s)",
        customer_id,
        len(enhancement_prompt),
    )

    # Send a simple prompt to trigger enhancement
    # The system prompt will guide the LLM to return the enhanced version
    simple_prompt = f"Enhance this concept: {user_input}"

    # Generate enhanced prompt - we need to manually handle streaming
    # to send events BEFORE completion
    from core.providers.factory import get_text_provider
    from features.chat.utils.generation_context import resolve_generation_context
    from features.chat.utils.prompt_utils import parse_prompt

    context = parse_prompt([{"type": "text", "text": simple_prompt}])
    provider, resolved_model, temperature, max_tokens = resolve_generation_context(
        prompt_text=context.text_prompt,
        settings=settings,
        customer_id=customer_id,
    )

    timings["text_request_sent_time"] = time.time()

    try:
        # Manually stream and collect chunks
        collected_chunks = []
        async for chunk in provider.stream(
            prompt=context.text_prompt,
            model=resolved_model,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=enhancement_prompt,
        ):
            text_chunk = str(chunk)
            collected_chunks.append(text_chunk)
            await manager.send_to_queues({"type": "text_chunk", "content": text_chunk})
            manager.collect_chunk(text_chunk, "text")

        enhanced_text = "".join(collected_chunks)
        timings["text_response_time"] = time.time()

        logger.info(
            "Prompt enhancement completed (customer=%s, enhanced_chars=%s)",
            customer_id,
            len(enhanced_text),
        )

        # Send enhanced prompt back to frontend BEFORE completing
        await manager.send_to_queues(
            {
                "type": "custom_event",
                "event_type": "promptEnhanced",
                "content": {
                    "enhanced_prompt": enhanced_text,
                    "original_input": user_input,
                },
            }
        )

        # If auto_generate_images is enabled, trigger image generation
        if auto_generate_images:
            logger.info("Auto-generating images for customer %s", customer_id)
            # TODO: Trigger image generation workflow
            # This would import and call the image generation logic
            await manager.send_to_queues(
                {
                    "type": "custom_event",
                    "event_type": "imageGenerationStarted",
                    "content": {
                        "prompt": enhanced_text,
                        "count": settings.get("image", {}).get("number_of_images", 4),
                    },
                }
            )

        await manager.send_to_queues(
            {
                "type": "custom_event",
                "event_type": "textGenerationCompleted",
                "content": {
                    "full_response": enhanced_text,
                    "metadata": {"is_enhancement": True},
                },
            }
        )

        return {"enhanced_prompt": enhanced_text}
    except asyncio.CancelledError:
        logger.info("Clarification workflow cancelled (customer=%s)", customer_id)
        raise
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Clarification workflow failed: %s", exc, exc_info=True)
        await manager.send_to_queues(
            {
                "type": "error",
                "content": f"Clarification workflow failed: {exc}",
                "stage": "clarification",
            }
        )
        raise
