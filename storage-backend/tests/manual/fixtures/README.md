# Audio Test Fixtures

This directory contains audio files used for manual testing.

## Required Files

### test_audio.wav
- **Format**: WAV (16-bit PCM)
- **Sample Rate**: 16000 Hz (recommended)
- **Channels**: Mono (1 channel)
- **Content**: Any clear speech audio for transcription testing
- **Purpose**: Used by Gemini manual tests

## Setup Instructions

1. Convert your M4A file to WAV format:
   ```bash
   ffmpeg -i your_audio.m4a -ar 16000 -ac 1 -sample_fmt s16 test_audio.wav
   ```

2. Place the converted file in this directory as `test_audio.wav`

3. Run tests with:
   ```bash
   GEMINI_MANUAL_AUDIO_PATH=/path/to/docker/storage-backend/tests/manual/fixtures/test_audio.wav RUN_MANUAL_TESTS=1 pytest tests/manual/test_gemini_audio_complete.py -v