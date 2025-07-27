#!/bin/bash
set -e

# List of models to pull from Ollama
models=(
  "mistral"
  "gemma:2b"
  "nous-hermes2"
)

for model in "${models[@]}"; do
  echo "Requesting pull of $model from Ollama API..."
  curl -X POST http://localhost:11434/api/pull -d '{"name": "'"$model"'", "stream":false}' -H "Content-Type: application/json"
done

echo "OK ! All models pulled using Ollama."
