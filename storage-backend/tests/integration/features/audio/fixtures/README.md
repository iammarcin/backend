# Audio Test Fixtures

## Available Audio Files

### `test_audio.wav`
- **Format**: WAV (PCM 16-bit)
- **Sample Rate**: 16kHz (suitable for Gemini and other 16kHz providers)
- **Channels**: Mono
- **Content**: Clear English speech (minimum 2-3 seconds)

### `test_audio_24khz.wav`
- **Format**: WAV (PCM 16-bit)
- **Sample Rate**: 24kHz (required by OpenAI Realtime API)
- **Channels**: Mono
- **Content**: Clear English speech (minimum 2-3 seconds)
- **Usage**: Use this file for OpenAI streaming integration tests

### Creating Proper Test Audio:
```bash
# Convert to 24kHz for OpenAI tests
ffmpeg -i input.wav -ar 24000 -ac 1 -acodec pcm_s16le test_audio_24khz.wav

# Convert to 16kHz for Gemini tests
ffmpeg -i input.wav -ar 16000 -ac 1 -acodec pcm_s16le test_audio.wav
```

### Expected Test Behavior:
- Tests should return non-empty transcription strings
- Transcription should contain recognizable English words
- VAD events should be triggered during speech

### If Tests Still Fail:
1. Check that OPENAI_API_KEY is valid and has Realtime API access
2. Verify the audio file contains actual speech (not silence)
3. Test with a known-good audio sample from OpenAI documentation
4. Check OpenAI API status and model availability