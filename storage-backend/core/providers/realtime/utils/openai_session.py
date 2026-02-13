"""Session configuration helpers for the OpenAI realtime provider.

`SessionConfig` encapsulates the normalisation logic required to translate the
user supplied provider settings into the payload expected by OpenAI's Realtime
API.  The helpers deliberately live in a dedicated module so that the main
provider class stays lean and focused on transport concerns.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Mapping

from config.realtime.providers import openai as openai_config


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SessionConfig:
    """Normalised session configuration used when communicating with OpenAI."""

    model: str
    voice: str | None
    temperature: float
    vad_enabled: bool
    enable_audio_input: bool
    enable_audio_output: bool
    tts_auto_execute: bool
    instructions: str | None

    @classmethod
    def from_settings(
        cls, settings: Mapping[str, object], *, default_model: str
    ) -> "SessionConfig":
        """Create a :class:`SessionConfig` from user supplied settings."""

        model = str(settings.get("model") or default_model)
        voice = settings.get("voice") or openai_config.DEFAULT_VOICE
        temperature = float(settings.get("temperature") or 0.7)
        vad_enabled = bool(settings.get("vad_enabled", True))
        enable_audio_input = bool(settings.get("enable_audio_input", True))
        tts_auto_execute = bool(settings.get("tts_auto_execute", False))
        requested_audio_output = bool(settings.get("enable_audio_output", True))
        enable_audio_output = requested_audio_output and tts_auto_execute
        instructions = settings.get("instructions")
        return cls(
            model=model,
            voice=str(voice) if voice else None,
            temperature=temperature,
            vad_enabled=vad_enabled,
            enable_audio_input=enable_audio_input,
            enable_audio_output=enable_audio_output,
            tts_auto_execute=tts_auto_execute,
            instructions=str(instructions) if instructions else None,
        )

    @property
    def websocket_url(self) -> str:
        """Return the websocket endpoint for the configured model."""

        return f"wss://api.openai.com/v1/realtime?model={self.model}"

    def to_session_update_event(self) -> dict[str, object]:
        """Return the ``session.update`` event payload for OpenAI."""

        modalities = self.output_modalities()

        session_body: dict[str, object] = {
            "type": "realtime",
            "model": self.model,
            "output_modalities": modalities,
        }

        if self.instructions:
            session_body["instructions"] = self.instructions

        audio_config: dict[str, object] = {}

        if self.enable_audio_input:
            input_config: dict[str, object] = {
                "format": {
                    "type": "audio/pcm",
                    "rate": openai_config.DEFAULT_SAMPLE_RATE,
                },
            }
            if self.vad_enabled:
                turn_detection: dict[str, object] | None = {
                    "type": "server_vad",
                    "threshold": openai_config.DEFAULT_TURN_DETECTION_THRESHOLD,
                    "prefix_padding_ms": openai_config.DEFAULT_TURN_DETECTION_PREFIX_PADDING_MS,
                    "silence_duration_ms": openai_config.DEFAULT_TURN_DETECTION_SILENCE_DURATION_MS,
                }
            else:
                turn_detection = None
            input_config["turn_detection"] = turn_detection
            transcription_config: dict[str, object] = {
                "model": "gpt-4o-transcribe",
            }
            input_config["transcription"] = transcription_config
            audio_config["input"] = input_config
        elif self.vad_enabled:
            logger.debug(
                "VAD requested but audio input disabled; disabling turn detection",
                extra={"model": self.model},
            )

        if self.enable_audio_output:
            output_config: dict[str, object] = {
                "format": {
                    "type": "audio/pcm",
                    "rate": openai_config.DEFAULT_SAMPLE_RATE,
                },
            }
            if self.voice:
                output_config["voice"] = self.voice
            audio_config["output"] = output_config

        if audio_config:
            session_body["audio"] = audio_config
        elif self.voice:
            session_body["voice"] = self.voice

        session_payload = {
            "type": "session.update",
            "session": session_body,
        }

        logger.info(
            "OpenAI Realtime session configuration",
            extra={
                "model": self.model,
                "output_modalities": modalities,
                "enable_audio_input": self.enable_audio_input,
                "enable_audio_output": self.enable_audio_output,
                "tts_auto_execute": self.tts_auto_execute,
                "voice": self.voice,
                "vad_enabled": self.vad_enabled,
                "temperature": self.temperature,
                "has_instructions": bool(self.instructions),
            },
        )
        logger.debug(
            "Full session.update payload being sent to OpenAI: %s",
            session_payload,
        )

        logger.debug(
            "Configured OpenAI turn detection",
            extra={
                "vad_enabled": self.vad_enabled,
                "turn_detection": (
                    audio_config.get("input", {}).get("turn_detection")
                    if audio_config
                    else None
                ),
            },
        )

        return session_payload

    def output_modalities(self) -> list[str]:
        """Return the output modalities to request from OpenAI."""

        if self.enable_audio_output:
            # OpenAI only allows a single modality; requesting audio yields speech plus transcripts.
            return ["audio"]
        return ["text"]


__all__ = ["SessionConfig"]
