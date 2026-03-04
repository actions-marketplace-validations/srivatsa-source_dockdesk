#!/bin/bash
# ───────────────────────────────────────────────────────────
# DockDesk - Test on any repo (Linux/macOS)
# ───────────────────────────────────────────────────────────
# Usage:
#   ./test_on_repo.sh https://github.com/fastapi/fastapi
#   ./test_on_repo.sh /path/to/local/repo
#   ./test_on_repo.sh https://github.com/pallets/flask --max-files 30
# ───────────────────────────────────────────────────────────

set -e

REPO_PATH="${1:?Usage: $0 <repo-url-or-path> [--max-files N] [--fast] [--full] [--keep]}"
shift

MAX_FILES=50
MODEL="qwen2.5-coder:3b"
REASONING_MODEL="deepseek-r1:1.5b"
FAST_FLAG=""
FULL=false
KEEP_CLONE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --max-files) MAX_FILES="$2"; shift 2 ;;
        --model) MODEL="$2"; shift 2 ;;
        --reasoning-model) REASONING_MODEL="$2"; shift 2 ;;
        --fast) FAST_FLAG="--fast"; shift ;;
        --full) FULL=true; shift ;;
        --keep) KEEP_CLONE=true; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

TEMP_DIR=""
TARGET_DIR=""

echo ""
echo "========================================"
echo "  DockDesk - Repo Test Runner"
echo "========================================"
echo ""

# ── Determine target directory ──
if [[ "$REPO_PATH" =~ ^https?:// ]]; then
    REPO_NAME=$(basename "$REPO_PATH" .git)
    TEMP_DIR="/tmp/dockdesk_test_${REPO_NAME}"

    if [ -d "$TEMP_DIR" ]; then
        echo "[*] Using existing clone: $TEMP_DIR"
    else
        echo "[*] Cloning $REPO_PATH ..."
        git clone --depth 1 "$REPO_PATH" "$TEMP_DIR"
    fi
    TARGET_DIR="$TEMP_DIR"
else
    if [ ! -d "$REPO_PATH" ]; then
        echo "Error: Path does not exist: $REPO_PATH"
        exit 1
    fi
    TARGET_DIR="$(cd "$REPO_PATH" && pwd)"
fi

# ── Count files ──
FILE_COUNT=$(find "$TARGET_DIR" -type f \
    -not -path "*/.git/*" \
    -not -path "*/node_modules/*" \
    -not -path "*/__pycache__/*" \
    -not -path "*/venv/*" \
    -not -path "*/dist/*" \
    -not -path "*/build/*" | wc -l | tr -d ' ')

echo "  Target:      $TARGET_DIR"
echo "  Total files: $FILE_COUNT"
echo "  Max files:   $MAX_FILES"
echo "  Model:       $MODEL"
echo "  Reasoning:   $REASONING_MODEL"
echo ""

# ── Smoke test ──
echo "────────────────────────────────────────"
echo "  Phase 1: Smoke Test (10 files, --fast)"
echo "────────────────────────────────────────"

SMOKE_START=$(date +%s)
dockdesk audit \
    --workspace "$TARGET_DIR" \
    --model "$MODEL" \
    --reasoning-model "$REASONING_MODEL" \
    --skip-rag \
    --max-files 10 \
    --fast || true
SMOKE_END=$(date +%s)
SMOKE_DURATION=$((SMOKE_END - SMOKE_START))

echo ""
echo "  Smoke test completed in ${SMOKE_DURATION}s"
echo ""

# ── Full run ──
echo "────────────────────────────────────────"
echo "  Phase 2: Full Audit"
echo "────────────────────────────────────────"

FULL_ARGS=(
    audit
    --workspace "$TARGET_DIR"
    --model "$MODEL"
    --reasoning-model "$REASONING_MODEL"
    --skip-rag
)

if [ "$FULL" = false ]; then
    FULL_ARGS+=(--max-files "$MAX_FILES")
fi

if [ -n "$FAST_FLAG" ]; then
    FULL_ARGS+=($FAST_FLAG)
fi

FULL_START=$(date +%s)
dockdesk "${FULL_ARGS[@]}" || true
FULL_END=$(date +%s)
FULL_DURATION=$((FULL_END - FULL_START))

echo ""
echo "────────────────────────────────────────"
echo "  Results Summary"
echo "────────────────────────────────────────"
echo "  Repo:         $TARGET_DIR"
echo "  Total files:  $FILE_COUNT"
echo "  Smoke test:   ${SMOKE_DURATION}s"
echo "  Full audit:   ${FULL_DURATION}s"

REPORT_PATH="$TARGET_DIR/audit_report.md"
if [ -f "$REPORT_PATH" ]; then
    echo "  Report:       $REPORT_PATH"
else
    echo "  Report:       (not generated)"
fi

DASH_PATH="$TARGET_DIR/dashboard_data.json"
if [ -f "$DASH_PATH" ]; then
    python3 -c "
import json
d = json.load(open('$DASH_PATH'))
files = d.get('latest_run_files', [])
high = sum(1 for f in files if f.get('risk') == 'HIGH')
med = sum(1 for f in files if f.get('risk') == 'MEDIUM')
low = sum(1 for f in files if f.get('risk') == 'LOW')
print(f'  Findings:     HIGH={high}  MEDIUM={med}  LOW={low}')
" 2>/dev/null || true
fi

echo ""

# ── Cleanup ──
if [ -n "$TEMP_DIR" ] && [ "$KEEP_CLONE" = false ]; then
    echo "[*] Cleaning up temp clone..."
    rm -rf "$TEMP_DIR"
fi

echo "Done."
