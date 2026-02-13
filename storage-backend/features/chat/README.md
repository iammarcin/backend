# Chat Feature - Request Types

## Audio Processing Modes

The chat feature supports multiple audio processing modes.

### 1. Standard Audio (STT → Text)

**Request type:** `audio`

**Flow:**
1. Frontend sends audio chunks.
2. Backend transcribes using the configured STT provider (Deepgram, Gemini, etc.).
3. Transcription text is sent to the LLM workflow.
4. LLM response is streamed back to the client.

**Configuration:**
```json
{
  "requestType": "audio",
  "userSettings": {
    "speech": {
      "model": "gemini-pro"
    }
  }
}
```

### 2. Audio Direct Mode (Multimodal)

**Request type:** `audio_direct` (auto-detected)

**Flow:**
1. Frontend sends audio chunks.
2. Backend collects all audio data.
3. Audio and the prompt are sent directly to a Gemini multimodal LLM.
4. The model interprets audio without a separate transcription step.
5. LLM response is streamed back to the client.

**Configuration:**
```json
{
  "requestType": "audio",
  "userSettings": {
    "speech": {
      "send_full_audio_to_llm": true
    }
  }
}
```

**When to use:**
- Situations where tone, emotion, or additional audio context is important.
- When transcription quality is insufficient.
- When a lower-latency path without STT is preferred.

**Model override:**
- `send_full_audio_to_llm=true` forces the Gemini multimodal models regardless of the configured STT model.
- Production default: `gemini-2.5-pro`.
- Development default: `gemini-2.5-flash`.
