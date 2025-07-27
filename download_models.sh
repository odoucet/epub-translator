#!/bin/bash
set -e

# List of models to pull from Ollama
models=(
  "gemma3:4b"
  "gemma3:12b"
  "gemma3:27b"
  "vera"
  "nous-hermes2"
)

for model in "${models[@]}"; do
  echo "Requesting pull of $model from Ollama API..."
  curl -s -X POST http://localhost:11434/api/pull -d '{"name": "'"$model"'", "stream":false}' -H "Content-Type: application/json" >/dev/null
  if [ $? -ne 0 ]; then
    echo "Error pulling model $model from Ollama API."
  fi
done

echo "OK ! All models pulled using Ollama."
