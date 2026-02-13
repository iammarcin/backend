# Manual Gemini & Live Provider Test Readiness Checklist

## Manual readiness at a glance

Use the matrix below to confirm which opt-in suites will run given your current environment. Each row corresponds to the tests that were skipped in the latest regression log. [F:docker/storage-backend/test.results.txt L124-L183]

| Suite | How to opt in | Extra assets | Notes |
| --- | --- | --- | --- |
| Gemini streaming + audio-direct (`tests/manual/test_gemini_*.py`) | `export RUN_MANUAL_TESTS=1` | 16-bit PCM WAV file, backend token | Requires the FastAPI backend to be up and Gemini credentials configured. [F:docker/storage-backend/tests/manual/test_gemini_audio_complete.py L1-L150] |
| OpenAI streaming smoke tests (`tests/manual/test_openai_streaming_*.py`) | `export RUN_MANUAL_TESTS=1` | Optional WAV file for the "complete" runner | Exercises the OpenAI streaming speech provider using either synthetic or real audio chunks. [F:docker/storage-backend/tests/manual/test_openai_streaming_basic.py L1-L48][F:docker/storage-backend/tests/manual/test_openai_streaming_complete.py L1-L117] |
| UFC database probe (`tests/manual/test_ufc_fighters_query.py`) | `export RUN_MANUAL_TESTS=1` | Connectivity to the UFC MySQL instance | Validates production-like data fetches and logs timings for QA sign-off. [F:docker/storage-backend/tests/manual/test_ufc_fighters_query.py L1-L56] |

Once the required variables and assets are present, rerun pytest to see the skips disappear.

## 1. Gemini manual verification flows (`tests/manual/test_gemini_*.py`)

The manual Gemini scripts stay skipped until you opt in with `RUN_MANUAL_TESTS`, a running backend, and a real WAV recording. [F:docker/storage-backend/tests/manual/test_gemini_streaming_manual.py L1-L27][F:docker/storage-backend/tests/manual/test_gemini_audio_complete.py L15-L33]

### 1.1 Prerequisites

| Requirement | Why it matters |
| --- | --- |
| `RUN_MANUAL_TESTS=1` exported in the backend container | Unskips the `pytest.mark.skipif` guard that hides the manual suites by default. [F:docker/storage-backend/tests/manual/test_gemini_streaming_manual.py L23-L26] |
| Valid `GOOGLE_API_KEY` in the environment | Ensures the Gemini SDK client initialises correctly and avoids the skip in the shared live-provider helper. [F:docker/storage-backend/tests/utils/live_providers.py L19-L33][F:docker/storage-backend/core/clients/ai.py L28-L42] |
| Backend FastAPI service running on `localhost:8000` | Both manual runners authenticate and push audio over the WebSocket endpoint. [F:docker/storage-backend/tests/manual/test_gemini_audio_complete.py L24-L81] |
| Test account credentials (`test@example.com` / `testpass`) available | The audio-complete workflow logs in through `/api/v1/auth/login` before sending audio. [F:docker/storage-backend/tests/manual/test_gemini_audio_complete.py L24-L37] |
| Real audio sample in uncompressed WAV (16-bit PCM) | The scripts stream the bytes chunk-by-chunk; PCM WAV avoids codec errors. [F:docker/storage-backend/tests/manual/test_gemini_streaming_manual.py L34-L67][F:docker/storage-backend/tests/manual/test_gemini_audio_complete.py L94-L151] |

### 1.2 Preparing the recording file

1. Record or export a 1–2 minute WAV clip (mono, 16 kHz, 16-bit PCM). Store it inside the repo (for example `tests/manual/samples/demo.wav`) or mount a host directory into the backend container so the file path is reachable from `/app`. [F:docker/docker-compose.yml L25-L52]
2. Confirm the backend container can see the path: `docker-compose exec backend ls /app/tests/manual/samples`.
3. Pass the absolute path when invoking the script, e.g. `python tests/manual/test_gemini_streaming_manual.py tests/manual/samples/demo.wav`. [F:docker/storage-backend/tests/manual/test_gemini_streaming_manual.py L85-L94]

### 1.3 Running the manual suites

```bash
# inside the backend container with the backend server already running
export RUN_MANUAL_TESTS=1
pytest tests/manual/test_gemini_streaming_manual.py -s
pytest tests/manual/test_gemini_audio_complete.py -s --maxfail=1
```

The audio-complete suite performs four sub-checks (streaming STT, audio-direct mode, history persistence, and error handling) and prints a summary so you can capture results for QA. [F:docker/storage-backend/tests/manual/test_gemini_audio_complete.py L86-L181]

## 2. OpenAI streaming manual exercises (`tests/manual/test_openai_streaming_*.py`)

The OpenAI streaming provider now has two manual harnesses:

* **`test_openai_streaming_basic.py`** – uses mock audio to verify connectivity without incurring audio-generation costs. Skip guard: `RUN_MANUAL_TESTS`. [F:docker/storage-backend/tests/manual/test_openai_streaming_basic.py L1-L48]
* **`test_openai_streaming_complete.py`** – feeds an on-disk WAV file through the provider to inspect latency and event ordering. When run as a script you can pass `--model both` to compare `gpt-4o-transcribe` and `gpt-4o-mini-transcribe`. [F:docker/storage-backend/tests/manual/test_openai_streaming_complete.py L1-L117]

### 2.1 Prerequisites

| Requirement | Why it matters |
| --- | --- |
| `RUN_MANUAL_TESTS=1` | Unskips both streaming scripts. [F:docker/storage-backend/tests/manual/test_openai_streaming_basic.py L12-L33] |
| `OPENAI_API_KEY` | Required for the streaming SDK client. Tests skip when missing. [F:docker/storage-backend/tests/integration/features/audio/test_openai_streaming_integration.py L1-L126] |
| Optional WAV sample | Needed only for `test_openai_streaming_complete.py` when you want to replay a real recording. |

### 2.2 Running the suite

```bash
export RUN_MANUAL_TESTS=1
pytest tests/manual/test_openai_streaming_basic.py -s
python tests/manual/test_openai_streaming_complete.py /path/to/audio.wav --model both
```

Inspect the streaming output to ensure deltas arrive and the transcription is populated; compare against the automated integration tests for parity. [F:docker/storage-backend/tests/integration/features/audio/test_openai_streaming_integration.py L42-L121]

## 3. UFC database manual verification (`tests/manual/test_ufc_fighters_query.py`)

UFC ingestion depends on production data and therefore remains opt-in. The manual script opens a real session, executes the `list_fighters_with_subscriptions` repository method, and logs diagnostics so you can capture timings for QA reports. [F:docker/storage-backend/tests/manual/test_ufc_fighters_query.py L1-L56]

### 3.1 Prerequisites

| Requirement | Why it matters |
| --- | --- |
| `RUN_MANUAL_TESTS=1` | Prevents the script from running without explicit approval. [F:docker/storage-backend/tests/manual/test_ufc_fighters_query.py L21-L32] |
| UFC database credentials in the environment | The repository builders pull connection strings from `core.utils.env`. |
| Network access to the UFC MySQL instance | Needed for both manual and automated Testcontainers-based suites. |

### 3.2 Executing the probe

```bash
export RUN_MANUAL_TESTS=1
pytest tests/manual/test_ufc_fighters_query.py -s
```

Capture the stdout logs; they include the number of fighters returned, total subscriptions, and elapsed time for historical comparisons. [F:docker/storage-backend/tests/manual/test_ufc_fighters_query.py L37-L54]

## 4. Live API provider smoke tests (`pytest -m live_api`)

Provider contract tests skip until each SDK client is initialised, which happens only when the corresponding API key is present. [F:docker/storage-backend/tests/utils/live_providers.py L19-L33][F:docker/storage-backend/core/clients/ai.py L28-L82] The `live_api` marker makes it easy to run them selectively. [F:docker/storage-backend/pytest.ini L6-L9]

### 4.1 Environment matrix

| Provider | Env var(s) required | Client key expected by tests | Sample test module |
| --- | --- | --- | --- |
| OpenAI | `OPENAI_API_KEY` | `openai_async` | `tests/unit/core/providers/text/test_message_alternation.py` (non-alternating messages). [F:docker/storage-backend/tests/unit/core/providers/text/test_message_alternation.py L90-L117] |
| Anthropic | `ANTHROPIC_API_KEY` | `anthropic_async` | `tests/manual/test_chat_history_manual.py` (history + thinking mode). [F:docker/storage-backend/tests/manual/test_chat_history_manual.py L17-L84] |
| Google Gemini | `GOOGLE_API_KEY` | `gemini` | Gemini cases remain skipped until the event-loop fixture lands, but the key must still be set to exercise them manually. [F:docker/storage-backend/tests/unit/core/providers/text/test_message_alternation.py L120-L156] |
| DeepSeek | `DEEPSEEK_API_KEY` | `deepseek_async` | DeepSeek alternation regression check. [F:docker/storage-backend/tests/unit/core/providers/text/test_message_alternation.py L56-L88] |
| Perplexity | `PERPLEXITY_API_KEY` | `perplexity_async` | Parameter mapping validation in `test_model_alias_parameters`. [F:docker/storage-backend/tests/unit/core/providers/text/test_model_alias_parameters.py L38-L109] |
| Groq | `GROQ_API_KEY` | `groq_async` | Reasoning/system prompt placement coverage. [F:docker/storage-backend/tests/unit/core/providers/text/test_system_prompt_placement.py L48-L132] |
| xAI | `XAI_API_KEY` | `xai_async` | System prompt placement smoke tests. [F:docker/storage-backend/tests/unit/core/providers/text/test_system_prompt_placement.py L133-L179] |

All of these variables are already forwarded into the backend container by `docker-compose.yml`; ensure your `.env` file on the host supplies real values before starting the stack. [F:docker/docker-compose.yml L31-L52]

### 4.2 Execution steps

1. Populate the required API keys in `.env` (host machine) and restart the backend container so `core.clients.ai` rebuilds the client cache with live SDK instances. Watch for the `Initialised <provider>` log lines in `docker logs backend`. [F:docker/storage-backend/core/clients/ai.py L28-L87]
2. Run `pytest -m live_api -s` from inside the backend container. Start with a focused subset if you're testing a single provider, e.g. `pytest -m live_api tests/manual/test_chat_history_manual.py -s`.
3. If a provider rate limits or rejects credentials, the helper converts those into skips so the suite reports the reason without failing the run. Investigate any other exceptions as real regressions. [F:docker/storage-backend/tests/utils/live_providers.py L36-L59]

### 4.3 Capturing artefacts

For reproducibility, archive:
- The pytest console output (`pytest -m live_api -s > live_api.log`).
- Relevant backend logs around each run (`docker logs backend > backend.log`).
- Any updated environment instructions or secrets hand-off docs.

This evidence accelerates cross-team debugging when third-party behaviour changes.

## 5. Replaying an xAI tool-call conversation

Use `tests/manual/test_http.sh` to sanity check the new tool-call flow end-to-end without writing a bespoke client. The script now emits a fourth request when attachment paths are provided.[F:docker/storage-backend/tests/manual/test_http.sh L1-L88]

1. Place a sample document and image inside the backend container so the FastAPI app can read them (for example under `/app/tests/manual/samples/`).
2. Export the paths before running the script:

```bash
export TOOL_FILE_PATH=/app/tests/manual/samples/tool-notes.md
export TOOL_IMAGE_PATH=/app/tests/manual/samples/mock-diagram.png
bash tests/manual/test_http.sh
```

3. The final `curl` call posts to `/chat/` with `prompt` items for text, image, and file attachments plus `settings.text.tools`. The response will echo `tool_calls`, `metadata.uploaded_file_ids`, and `requires_tool_action` so you can confirm the behaviour the frontend expects.[F:docker/storage-backend/tests/manual/test_http.sh L52-L88][F:docker/storage-backend/core/providers/text/xai.py L152-L205]
