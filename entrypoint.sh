#!/bin/bash

# Start Ollama in the background
echo "Starting Ollama Server..."
ollama serve &

# Wait for Ollama to wake up
echo "Waiting for Ollama API..."
until curl -s http://localhost:11434/api/tags > /dev/null; do
    sleep 1
done

# Check if model exists, if not pull it (this happens at runtime)
# We use the MODEL_NAME env var or default
MODEL=${MODEL_NAME:-"qwen2.5-coder:3b"}

if ! ollama list | grep -q "$MODEL"; then
    echo "Model $MODEL not found. Pulling..."
    ollama pull $MODEL
else
    echo "Model $MODEL found. Skipping pull."
fi

# Run the auditor
echo "Starting Neural Auditor..."
python /app/auditor_slm.py --ci
