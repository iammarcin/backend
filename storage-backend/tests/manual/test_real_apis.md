# Manual Testing Checklist for Streaming TTS Pipeline

## Prerequisites
- Backend environment running with streaming TTS changes
- Valid ElevenLabs API key configured
- Valid OpenAI or Anthropic API key configured

## Test Cases

### 1. Basic Parallel Streaming
- [ ] Start the backend server
- [ ] Enable TTS auto-execute in the client
- [ ] Select ElevenLabs as the TTS provider
- [ ] Send a prompt such as "Tell me a story about a robot"
- [ ] Verify that:
  - [ ] Text begins streaming to the UI immediately
  - [ ] Audio starts playing before the text finishes
  - [ ] Text and audio complete successfully
  - [ ] Audio file uploads to S3
  - [ ] No errors appear in backend logs

### 2. Different Text Lengths
- [ ] Short text (1 sentence)
- [ ] Medium text (1 paragraph)
- [ ] Long text (multiple paragraphs)

### 3. Different Voices
- [ ] Sherlock
- [ ] Naval
- [ ] Allison

### 4. Different Models
- [ ] eleven_turbo_v2_5
- [ ] eleven_multilingual_v2
- [ ] eleven_monolingual_v1

### 5. Error Scenarios
- [ ] Invalid API key triggers graceful failure
- [ ] Simulated network timeout handles retry/cleanup
- [ ] Cancel request mid-stream clears queues without leaks

### 6. Performance Validation
- [ ] Measure time to first audio chunk (< 2 seconds)
- [ ] Measure total completion time (~2 seconds for short prompts)
- [ ] Compare against legacy backend performance targets

### 7. Backward Compatibility
- [ ] Disable TTS auto-execute and confirm text-only workflow works
- [ ] Use non-streaming providers and confirm fallback to buffered mode
- [ ] Execute existing chat flows without TTS and verify no regressions

## Success Criteria
- [ ] All manual tests pass
- [ ] No unexpected errors in logs
- [ ] User experience meets latency goals
