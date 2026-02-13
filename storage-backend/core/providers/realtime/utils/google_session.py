"""Session configuration helpers for the Google Gemini Live provider.

This module defines the internal dataclass that stores all runtime
configuration for a Gemini Live realtime session and exposes a helper for
producing the websocket setup payload expected by the API.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class GoogleSessionConfig:
    """Internal representation of Gemini Live session settings."""

    model: str
    voice: str | None
    temperature: float
    enable_audio_input: bool
    enable_audio_output: bool
    tts_auto_execute: bool
    live_translation: bool
    translation_language: str | None

    def to_setup_event(self) -> dict[str, object]:
        """Return the setup payload forwarded to the Gemini websocket."""

        response_modalities: list[str] = ["TEXT"]
        if self.enable_audio_output:
            if self.tts_auto_execute:
                response_modalities = ["AUDIO"]
            elif "AUDIO" not in response_modalities:
                response_modalities.append("AUDIO")

        generation_config: dict[str, object] = {
            "response_modalities": response_modalities,
            "temperature": self.temperature,
        }
        if self.voice:
            generation_config["speech_config"] = {
                "voice_config": {"prebuilt_voice_config": {"voice_name": self.voice}}
            }
        if self.translation_language:
            generation_config["language_code"] = self.translation_language

        setup_payload: dict[str, object] = {
            "setup": {
                "model": self.model,
                "generation_config": generation_config,
            }
        }

        if self.enable_audio_input:
            setup_payload["setup"]["input_options"] = {"enable_audio": True}

        return setup_payload


__all__ = ["GoogleSessionConfig"]

