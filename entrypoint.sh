#!/bin/bash
set -e

# ============================================
# DockDesk Neural Auditor - GitHub Action Entry
# ============================================

echo "🛡️ DockDesk Neural Auditor"
echo "=========================="

# Use external Ollama service (GitHub Actions service container)
OLLAMA_HOST=${DOCKDESK_OLLAMA_HOST:-"http://localhost:11434"}
export OLLAMA_HOST

echo "Connecting to Ollama at $OLLAMA_HOST..."
MAX_WAIT=30
WAITED=0
until curl -s --connect-timeout 2 "$OLLAMA_HOST/api/tags" > /dev/null 2>&1; do
    sleep 1
    WAITED=$((WAITED + 1))
    if [ $WAITED -ge $MAX_WAIT ]; then
        echo "::error::Ollama service not reachable at $OLLAMA_HOST"
        echo "::error::Ensure Ollama service container is running in your workflow:"
        echo "::error::  services:"
        echo "::error::    ollama:"
        echo "::error::      image: ollama/ollama:latest"
        echo "::error::      ports:"
        echo "::error::        - 11434:11434"
        exit 1
    fi
done
echo "✓ Ollama service ready"

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
    
    # Check if model exists, pull if needed via API
    echo "Checking model availability..."
    if ! curl -s "$OLLAMA_HOST/api/tags" | grep -q "$MODEL"; then
        echo "Model $MODEL not found. Pulling (this may take a few minutes)..."
        curl -X POST "$OLLAMA_HOST/api/pull" -d "{\"name\": \"$MODEL\"}" -H "Content-Type: application/json" --max-time 600 || {
            echo "::error::Failed to pull model '$MODEL'"
            echo "Ensure model is pre-pulled in workflow or try: qwen2.5-coder:3b"
            exit 1
        }
        echo "✓ Model pulled successfully"
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

exit $EXIT_CODE
