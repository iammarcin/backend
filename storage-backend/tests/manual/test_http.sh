#!/bin/bash

set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"

printf "Testing POST /chat endpoint...\n================================\n"

curl -sS -X POST "${BASE_URL}/chat/" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Write a haiku about APIs",
    "settings": {
      "text": {
        "model": "gpt-4o-mini",
        "temperature": 0.7
      }
    },
    "customer_id": 1
  }' | jq

printf "\n\nTesting POST /chat/stream endpoint...\n======================================\n"

curl -sS -X POST "${BASE_URL}/chat/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Count from 1 to 5",
    "settings": {
      "text": {
        "model": "gpt-4o-mini"
      }
    },
    "customer_id": 1
  }'

printf "\n\nTesting session name generation...\n==================================\n"

curl -sS -X POST "${BASE_URL}/chat/session-name" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What is machine learning?",
    "settings": {},
    "customer_id": 1
  }' | jq

if [[ -n "${TOOL_FILE_PATH:-}" && -n "${TOOL_IMAGE_PATH:-}" ]]; then
  printf "\n\nReplaying tool-call conversation with attachments...\n====================================================\n"

  FILE_PATH=$(python - <<'PY'
import os, sys
print(os.path.abspath(sys.argv[1]))
PY
"${TOOL_FILE_PATH}")
  IMAGE_PATH=$(python - <<'PY'
import os, sys
print(os.path.abspath(sys.argv[1]))
PY
"${TOOL_IMAGE_PATH}")

  REQUEST_PAYLOAD=$(jq -n \
    --arg image_url "${IMAGE_PATH}" \
    --arg file_url "${FILE_PATH}" \
    --arg file_name "$(basename "${TOOL_FILE_PATH}")" \
    '{
      prompt: [
        {type: "text", text: "Summarise the uploaded artefacts"},
        {type: "image_url", image_url: {url: $image_url, detail: "high"}},
        {type: "file_url", file_url: {url: $file_url, filename: $file_name}}
      ],
      settings: {
        text: {
          model: "grok-4",
          tools: {
            functions: [
              {
                name: "extract_metadata",
                description: "Summarise attachment metadata",
                parameters: {
                  type: "object",
                  properties: {
                    city: {type: "string"},
                    attachments: {type: "integer"}
                  }
                }
              }
            ],
            tool_choice: {type: "auto"}
          }
        }
      },
      customer_id: 1
    }')

  echo "${REQUEST_PAYLOAD}" | curl -sS -X POST "${BASE_URL}/chat/" \
    -H "Content-Type: application/json" \
    -d @- | jq
else
  printf "\nSet TOOL_FILE_PATH and TOOL_IMAGE_PATH to replay a tool-call conversation (paths must be visible to the backend container).\n"
fi
