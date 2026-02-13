from __future__ import annotations

from features.realtime.context import RealtimeTurnContext


def test_append_live_translation_accumulates_and_finalises() -> None:
    context = RealtimeTurnContext()

    context.append_live_translation("  Hola ")
    context.append_live_translation("mundo")

    assert context.live_translation_text == "Hola mundo"

    context.append_live_translation("Gracias por venir", is_final=True)

    assert context.live_translation_text == "Gracias por venir"
    assert context.live_translation_parts == []


def test_append_live_translation_handles_empty_final_payload() -> None:
    context = RealtimeTurnContext()

    context.append_live_translation("Buenos dias")
    context.append_live_translation("", is_final=True)

    assert context.live_translation_text == "Buenos dias"

    context.reset()

    assert context.live_translation_text is None
    assert context.live_translation_parts == []
