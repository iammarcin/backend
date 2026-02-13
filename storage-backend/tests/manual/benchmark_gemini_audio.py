"""Performance benchmarks for Gemini audio workflows."""

from __future__ import annotations

import asyncio
import time
from statistics import mean, stdev
from typing import Callable

import httpx

from tests.manual.test_gemini_audio_complete import _authenticate, _send_audio_over_websocket

BASE_URL = "http://127.0.0.1:8000"


async def _load_audio_fixture() -> tuple[bytes, int]:
    import wave
    from pathlib import Path

    audio_file = Path("tests/fixtures/test_audio.wav")
    with wave.open(str(audio_file), "rb") as wf:
        sample_rate = wf.getframerate()
        audio_bytes = wf.readframes(wf.getnframes())
    return audio_bytes, sample_rate


async def _benchmark(
    *,
    num_runs: int,
    runner: Callable[[str, bytes, int], asyncio.Future[list[dict[str, object]]]],
    label: str,
) -> None:
    async with httpx.AsyncClient() as client:
        token = await _authenticate(client)

    audio_bytes, sample_rate = await _load_audio_fixture()

    latencies: list[float] = []
    for run in range(num_runs):
        start = time.perf_counter()
        events = await runner(token, audio_bytes, sample_rate)
        end = time.perf_counter()

        latencies.append(end - start)
        print(f"{label} run {run + 1}: {latencies[-1]:.2f}s, events={len(events)}")

    print("\n===", label, "Benchmark Results ===")
    print(f"Mean: {mean(latencies):.2f}s")
    if len(latencies) > 1:
        print(f"StdDev: {stdev(latencies):.2f}s")
    print(f"Min: {min(latencies):.2f}s")
    print(f"Max: {max(latencies):.2f}s")


async def _run_streaming(token: str, audio_bytes: bytes, sample_rate: int) -> list[dict[str, object]]:
    return await _send_audio_over_websocket(
        token=token,
        request_type="audio",
        speech_settings={
            "model": "gemini-2.5-flash",
            "recording_sample_rate": sample_rate,
        },
        audio_bytes=audio_bytes,
    )


async def _run_audio_direct(token: str, audio_bytes: bytes, sample_rate: int) -> list[dict[str, object]]:
    return await _send_audio_over_websocket(
        token=token,
        request_type="audio",
        speech_settings={
            "model": "gemini-2.5-flash",
            "recording_sample_rate": sample_rate,
            "send_full_audio_to_llm": True,
        },
        audio_bytes=audio_bytes,
    )


async def main(num_runs: int = 5) -> None:
    print("Starting Gemini audio benchmarks...")
    await _benchmark(num_runs=num_runs, runner=_run_streaming, label="Gemini Streaming STT")
    await _benchmark(num_runs=num_runs, runner=_run_audio_direct, label="Audio Direct Mode")


if __name__ == "__main__":
    asyncio.run(main())
