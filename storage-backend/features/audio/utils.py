"""Utility functions for audio data manipulation."""

from __future__ import annotations

import logging
from typing import Final

import numpy as np
from scipy import signal

logger = logging.getLogger(__name__)

_INT16_MAX: Final[int] = np.iinfo(np.int16).max
_INT16_MIN: Final[int] = np.iinfo(np.int16).min


def resample_audio(audio_data: bytes, original_rate: int, target_rate: int) -> bytes:
    """Return audio bytes resampled from ``original_rate`` to ``target_rate``.

    Audio data is expected to be raw PCM ``int16`` bytes. When the sample rates
    match the input is returned unchanged. Any exception during resampling is
    logged and the original audio is returned to avoid interrupting streaming
    flows. The caller can decide how to handle potential incompatibilities with
    the downstream provider.
    """

    if original_rate == target_rate:
        return audio_data

    if not audio_data:
        return audio_data

    try:
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        if audio_array.size == 0:
            return audio_data

        num_samples = int(round(audio_array.size * target_rate / original_rate))
        if num_samples <= 0:
            logger.warning(
                "Calculated non-positive number of samples during resample: %s", num_samples
            )
            return audio_data

        resampled = signal.resample(audio_array, num_samples)
        clipped = np.clip(resampled, _INT16_MIN, _INT16_MAX).astype(np.int16)
        return clipped.tobytes()
    except Exception as exc:  # pragma: no cover - best effort logging
        logger.error("Failed to resample audio from %sHz to %sHz: %s", original_rate, target_rate, exc)
        return audio_data


def bytes_to_audio_array(audio_data: bytes) -> np.ndarray:
    """Convert raw PCM ``int16`` bytes to a NumPy array."""

    if not audio_data:
        return np.array([], dtype=np.int16)
    return np.frombuffer(audio_data, dtype=np.int16)


def audio_array_to_bytes(audio_array: np.ndarray) -> bytes:
    """Convert a NumPy ``int16`` array back into raw PCM bytes."""

    if audio_array.size == 0:
        return b""
    return audio_array.astype(np.int16).tobytes()
