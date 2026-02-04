#!/bin/bash
set -e

# ============================================
# DockDesk Neural Auditor - GitHub Action Entry
# ============================================

echo "🛡️ DockDesk Neural Auditor"
echo "=========================="

# Check if external Ollama is available (e.g., from a service container)
OLLAMA_HOST=${DOCKDESK_OLLAMA_HOST:-"http://localhost:11434"}
EXTERNAL_OLLAMA=false

echo "Checking for Ollama at $OLLAMA_HOST..."
if curl -s --connect-timeout 5 "$OLLAMA_HOST/api/tags" > /dev/null 2>&1; then
    echo "✓ External Ollama service detected at $OLLAMA_HOST"
    EXTERNAL_OLLAMA=true
    export OLLAMA_HOST
else
    # Start local Ollama in the background
    echo "Starting local Ollama Server..."
    ollama serve &
    OLLAMA_PID=$!
    
    # Wait for Ollama to wake up
    echo "Waiting for Ollama API..."
    MAX_WAIT=60
    WAITED=0
    until curl -s http://localhost:11434/api/tags > /dev/null 2>&1; do
        sleep 1
        WAITED=$((WAITED + 1))
        if [ $WAITED -ge $MAX_WAIT ]; then
            echo "::error::Ollama failed to start within ${MAX_WAIT}s"
            exit 1
        fi
    done
    OLLAMA_HOST="http://localhost:11434"
fi
echo "✓ Ollama ready"

# Configuration from environment
MODEL=${MODEL_NAME:-"qwen2.5-coder:3b"}
AUTO_TUNE=${DOCKDESK_AUTO_TUNE:-"false"}
FAIL_ON_RISK=${DOCKDESK_FAIL_ON_RISK:-"HIGH"}
OUTPUT_FORMAT=${DOCKDESK_OUTPUT_FORMAT:-"md"}
AUTO_FIX=${DOCKDESK_AUTO_FIX:-"false"}
WORKSPACE=${DOCKDESK_WORKSPACE:-"."}

# Audit-suitable models allowlist
AUDIT_MODELS=(
    "qwen2.5-coder:1.5b"
    "qwen2.5-coder:3b"
    "qwen2.5-coder:7b"
    "qwen2.5-coder:14b"
    "codellama:7b"
    "codellama:13b"
    "deepseek-coder:1.3b"
    "deepseek-coder:6.7b"
    "deepseek-coder:33b"
    "starcoder2:3b"
)

# Validate model is audit-suitable
validate_model() {
    local model=$1
    local base_model=$(echo "$model" | cut -d':' -f1)
    
    for allowed in "${AUDIT_MODELS[@]}"; do
        allowed_base=$(echo "$allowed" | cut -d':' -f1)
        if [[ "$base_model" == "$allowed_base" ]]; then
            return 0
        fi
    done
    return 1
}

# Model selection guidance
if [[ "$AUTO_TUNE" == "true" ]]; then
    echo "📊 Auto-tune enabled - model will be selected based on codebase size"
else
    echo "🧠 Model: $MODEL"
    
    if ! validate_model "$MODEL"; then
        echo "::warning::Model '$MODEL' is not in the audit-suitable allowlist."
        echo "Recommended models for semantic auditing:"
        echo "  Small (<10k LOC):  qwen2.5-coder:3b, qwen2.5-coder:1.5b"
        echo "  Medium (10-50k):   qwen2.5-coder:7b, codellama:7b"
        echo "  Large (>50k):      qwen2.5-coder:14b, codellama:13b"
        echo ""
        echo "Proceeding with '$MODEL' - results may vary."
    fi
    
    # Pull model if needed
    if ! ollama list | grep -q "$MODEL"; then
        echo "Model $MODEL not found. Pulling..."
        if ! ollama pull "$MODEL"; then
            echo "::error::Failed to pull model '$MODEL'"
            echo "Check model name or try: qwen2.5-coder:3b"
            exit 1
        fi
    else
        echo "✓ Model $MODEL available"
    fi
fi

# Build CLI arguments
CLI_ARGS="--ci --workspace $WORKSPACE --fail-on-risk $FAIL_ON_RISK --format $OUTPUT_FORMAT"

if [[ "$AUTO_TUNE" == "true" ]]; then
    CLI_ARGS="$CLI_ARGS --auto-tune"
else
    CLI_ARGS="$CLI_ARGS --model $MODEL"
fi

if [[ "$AUTO_FIX" == "true" ]]; then
    CLI_ARGS="$CLI_ARGS --fix"
fi

# Run the auditor
echo ""
echo "🔍 Starting Semantic Audit..."
echo "   Workspace: $WORKSPACE"
echo "   Fail threshold: $FAIL_ON_RISK"
echo "   Output: $OUTPUT_FORMAT"
echo ""

cd /github/workspace
python /app/auditor_slm.py $CLI_ARGS
EXIT_CODE=$?

# Cleanup
if [ "$EXTERNAL_OLLAMA" = "false" ] && [ -n "$OLLAMA_PID" ]; then
    kill $OLLAMA_PID 2>/dev/null || true
fi

exit $EXIT_CODE
