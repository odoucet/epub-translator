#!/bin/bash
set -e

# List of models to pull from Ollama
models=(
  "gemma3:4b"
  "gemma3:12b"
  "gemma3:27b"
  "dorian2b/vera"
  "nous-hermes2"
)

for model in "${models[@]}"; do
  echo "Requesting pull of $model from Ollama API..."
  curl -s -X POST http://localhost:11434/api/pull -d '{"name": "'"$model"'", "stream":true}' -H "Content-Type: application/json" | while read -r line; do
    if [[ $line == *"error"* ]]; then
      echo "Error pulling model $model: $line"
      exit 1
    else
      # Remove any newlines and carriage returns from the line
      clean_line=$(echo "$line" | tr -d '\n\r')
      echo -ne "Pulling model $model: $clean_line\r"
    fi
  done
  echo -e "\nModel $model pulled successfully."
done

echo "OK ! All models pulled using Ollama."
