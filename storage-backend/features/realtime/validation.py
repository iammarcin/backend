"""Audio validation utilities for realtime sessions."""

from __future__ import annotations

from array import array


class AudioValidationError(Exception):
    """Raised when realtime audio validation fails."""


_PCM16_SAMPLE_RATE = 24_000
_PCM16_BYTES_PER_SAMPLE = 2
_PCM16_MIN_SECONDS = 1
_PCM16_MAX_SECONDS = 60 * 10
_PCM16_INSPECTION_SAMPLES = 5_000


def _pcm16_limits() -> tuple[int, int]:
    """Return minimum and maximum byte lengths for PCM16 validation."""

    min_bytes = _PCM16_SAMPLE_RATE * _PCM16_BYTES_PER_SAMPLE * _PCM16_MIN_SECONDS
    max_bytes = _PCM16_SAMPLE_RATE * _PCM16_BYTES_PER_SAMPLE * _PCM16_MAX_SECONDS
    return min_bytes, max_bytes


def validate_pcm16_audio(audio_bytes: bytes) -> tuple[bool, str]:
    """Validate PCM16 mono audio payloads."""

    if not audio_bytes:
        return False, "Audio data is empty"

    min_bytes, max_bytes = _pcm16_limits()
    byte_count = len(audio_bytes)

    if byte_count < min_bytes:
        return False, f"Audio too short: {byte_count} bytes (min {min_bytes})"

    if byte_count > max_bytes:
        return False, f"Audio too long: {byte_count} bytes (max {max_bytes})"

    if byte_count % _PCM16_BYTES_PER_SAMPLE != 0:
        return False, f"Invalid PCM16 size: {byte_count} (must be even)"

    # Inspect a bounded subset of samples to avoid excessive allocations.
    inspect_count = min(byte_count // _PCM16_BYTES_PER_SAMPLE, _PCM16_INSPECTION_SAMPLES)
    if inspect_count == 0:
        return False, "Audio payload too small for validation"

    samples = array("h")
    samples.frombytes(audio_bytes[: inspect_count * _PCM16_BYTES_PER_SAMPLE])

    if all(sample == 0 for sample in samples):
        return False, "Audio appears to be silent (all zeros)"

    max_value = 32767
    min_value = -32768
    clipped = sum(1 for sample in samples if sample in {max_value, min_value})
    if clipped / len(samples) > 0.5:
        return False, "Audio severely clipped"

    return True, ""


def validate_audio_format(audio_bytes: bytes, *, expected_format: str = "pcm16") -> None:
    """Validate realtime audio payloads before uploading to storage."""

    if expected_format.lower() == "pcm16":
        is_valid, error_message = validate_pcm16_audio(audio_bytes)
        if not is_valid:
            raise AudioValidationError(error_message)
        return

    raise AudioValidationError(f"Unsupported format: {expected_format}")


__all__ = [
    "AudioValidationError",
    "validate_audio_format",
    "validate_pcm16_audio",
]

