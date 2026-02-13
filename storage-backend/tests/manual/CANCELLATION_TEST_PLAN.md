# WebSocket Cancellation – Manual Test Plan

This checklist verifies the end-user experience for the WebSocket cancellation feature across the chat frontends. Execute the tests in order on both the React and Kotlin apps when validating a release.

## Environment

- Backend: `storage-backend` running locally or in staging with verbose logging enabled
- Frontend: React web app or Kotlin app connected to the same backend
- Monitoring: Tail `docker-compose logs -f storage-backend` (or equivalent) while testing

## Test Cases

### TC1 – Cancel Long Text Generation
1. Start a chat and submit: “Write a 3,000 word essay about the history of computers.”
2. Wait for `text` chunks to stream, then click **Cancel**.
3. Expected: UI shows “Cancelling…” immediately, backend logs `Workflow cancelled by user`, frontend receives `cancelled`, `textNotRequested`, `ttsNotRequested`, and `fullProcessComplete` events.
4. After acknowledgement, send another short prompt and confirm it runs normally.

### TC2 – Cancel With No Active Request
1. Open chat with no in-flight request.
2. Click **Cancel**.
3. Expected: No errors; backend logs “Cancel requested but no workflow running”; UI remains idle.

### TC3 – Cancel Then New Request
1. Send a long-running prompt.
2. Cancel mid-stream.
3. Immediately send a short prompt (“Say hello”).
4. Expected: First request terminates gracefully; second request processes without “Prompt required” errors.

### TC4 – Rapid Cancel/Start Cycle
1. Loop 10 times: send a prompt, wait <1s, press **Cancel**.
2. Expected: No WebSocket disconnects, no duplicate completions, UI remains responsive.

### TC5 – Cancel During TTS Playback
1. Enable TTS autoplay in settings.
2. Send a prompt that triggers audio playback.
3. Cancel while TTS audio is playing.
4. Expected: Audio stops (or completes if too close to finishing) with a `cancelled` event; no stuck progress bars.

### TC6 – Cancel Deep Research Workflow
1. Enable deep research mode.
2. Start a research query (“Compare CUDA and ROCm roadmaps…”).
3. Cancel during the “Researching…” stage.
4. Expected: Research stops, no partial summaries saved, backend logs cancellation at `stage=execution`.

### TC7 – Cancel Audio Upload
1. Record audio input (STT workflow).
2. Cancel during transcription.
3. Expected: Upload halts, no orphaned audio chunks, UI ready for next recording.

## Regression Checks

- **RT1:** Send 10 normal requests without cancelling; ensure no latency regressions.
- **RT2:** Send control events (`ping`, `heartbeat`, `close_session`) while a workflow is running; verify they still work.

## Acceptance Criteria

- All cancellation flows emit `cancelled`, `textNotRequested`, `ttsNotRequested`, and `fullProcessComplete` in order.
- Backend logs show `Workflow cancelled by user (session=…)`.
- No “Prompt required” or “Attempted to send to a completed stream” errors.
- UI becomes ready for a new request within 2 seconds.

Document pass/fail results and attach backend logs for failed scenarios before sign-off.
