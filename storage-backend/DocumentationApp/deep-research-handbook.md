# Deep Research Workflow

## Overview

Deep research orchestrates a three-stage workflow that transforms a user's
question into a conversational answer backed by web citations. When enabled via
chat settings the backend coordinates prompt optimisation, Perplexity research,
and conversational analysis while persisting intermediate artefacts.

## Workflow Stages

1. **Prompt Optimisation** – The user's latest message plus recent chat history
   are distilled into a detailed research prompt using the user's primary model.
   The request falls back to the original query if optimisation fails.
2. **Research Execution** – The optimised prompt is sent to Perplexity's
   `sonar-deep-research` model with factual settings (temperature `0.2`,
   `max_tokens` `2048`). Citations returned by Perplexity are captured.
3. **Conversational Analysis** – The formal research report is converted into a
   friendly response by the user's primary model. The result is streamed back to
   the client together with metadata and citations.

## Enabling Deep Research

```json
{
  "prompt": [{"type": "text", "text": "What are the latest breakthroughs in quantum computing?"}],
  "settings": {
    "text": {
      "model": "gpt-4o",
      "deep_research_enabled": true,
      "deep_research_model": "perplexity"
    }
  },
  "customer_id": 123,
  "session_id": "optional-session-uuid"
}
```

Deep research requires a configured primary model and currently supports the
Perplexity provider only.

## WebSocket Events

During the workflow the backend emits a series of custom events:

1. `deepResearchStarted` – Workflow initialisation.
2. `deepResearchOptimizing` – Prompt optimisation in progress.
3. `deepResearchSearching` – Perplexity research underway (includes the
   optimised prompt preview).
4. `deepResearchAnalyzing` – Conversational analysis stage.
5. `citations` – Citations forwarded with the streamed response metadata.
6. `deepResearchCompleted` – Workflow finished with citation counts and the
   `notification` tag marker.

## Database Persistence

* Optimised prompt stored as a **user** message linked to the session.
* Research report stored as an **AI** message using model name
  `sonar-deep-research` and enriched Claude-code metadata containing citations.
* Sessions are tagged with `notification` so the frontend can highlight deep
  research results.

## Response Metadata

The streamed payload includes an `is_deep_research` flag and a
`research_metadata` object containing:

* `stage_count` – Number of workflow stages (always `3`).
* `citations_count` – Number of Perplexity citations captured.
* `notification_tagged` – Indicates whether the session already contains the
  `notification` tag.
* `message_ids` – Identifiers for the persisted user and AI messages.
* `stage_timings` – Durations for optimisation, research, and analysis phases.

## Configuration

Configuration defaults live in
`features/chat/services/streaming/deep_research_config.py`:

* Default provider: `perplexity`.
* Optimisation temperature: `0.2`.
* Optimisation max tokens: `800`.
* Research temperature: `0.2`.
* Research max tokens: `2048`.

The validation helper ensures `deep_research_enabled` is set and a primary model
is configured. Unsupported research models automatically fall back to the
Perplexity default.

## Performance Expectations

* Optimisation: < 10 seconds.
* Research: 30–90 seconds depending on the query.
* Analysis: 10–30 seconds.

The orchestrator logs structured timing information for each stage to aid
observability.

## Error Handling

* Optimisation failures fall back to the original query with a date prefix.
* Research errors propagate as `HTTP 502` responses with a descriptive event.
* Analysis failures stream the raw research report so the user still receives
  useful information.
* Persistence issues are logged but never abort the response stream.

## Testing

* Unit tests cover orchestrator routing, persistence helpers, and event
  emission.
* End-to-end style tests mock provider responses and verify database persistence
  using in-memory stubs.
* Run focused tests with:

```bash
pytest tests/unit/features/chat/services/streaming/test_deep_research.py -v
pytest tests/unit/features/chat/services/streaming/test_deep_research_persistence.py -v
```

## Legacy Parity

The workflow mirrors the legacy backend behaviour while modernising the
architecture:

* The optimised prompt and research report are persisted exactly once.
* Citation metadata is preserved alongside the AI response.
* Session tagging retains pre-existing user tags via additive updates.
* Progress events follow the same structure for frontend compatibility.

Refer to `DocumentationApp/deep-research-implementation-context.md` for detailed
architecture notes and design decisions across all milestones.
