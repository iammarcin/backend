"""Prompts for audio transcription and translation.

Edit these to customize AI behavior when transcribing audio.
"""

from __future__ import annotations


DEFAULT_TRANSCRIBE_PROMPT = """Generate a transcript of the provided audio recording.
Follow these rules:
- Provide only the text transcription (without meta comments, timestamps, or sound descriptions).
- Exclude filler words and interjections such as "uh", "um", "ah", "oh", "hmm", etc. - do not include them in the transcript.
- If there is no speech or the audio contains only noise/music/silence, return an empty string.
- Do not add any explanatory text about the audio content."""


DEFAULT_TRANSLATE_PROMPT = """Translate the provided audio into {language} and return the translated transcript."""


__all__ = ["DEFAULT_TRANSCRIBE_PROMPT", "DEFAULT_TRANSLATE_PROMPT"]
