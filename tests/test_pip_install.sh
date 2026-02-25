#!/usr/bin/env bash
# ───────────────────────────────────────────────────────────
# DockDesk - Pip Install Integration Test (Linux/macOS)
# ───────────────────────────────────────────────────────────
# Tests: fresh venv → pip install → dockdesk --help → audit small repo → verify outputs
#
# Usage:
#   ./tests/test_pip_install.sh
#   ./tests/test_pip_install.sh https://github.com/psf/httpbin
# ───────────────────────────────────────────────────────────

set -e

TEST_REPO="${1:-https://github.com/pallets/click}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # project root
VENV_DIR="/tmp/dockdesk_pip_test_venv"
CLONE_DIR="/tmp/dockdesk_pip_test_repo"
FAILED=0
TOTAL=0

test_step() {
    local name="$1"
    shift
    TOTAL=$((TOTAL + 1))
    printf "  [%s] ..." "$name"
    if "$@" > /dev/null 2>&1; then
        echo " OK"
    else
        echo " FAIL"
        FAILED=$((FAILED + 1))
    fi
}

echo ""
echo "========================================"
echo "  DockDesk - Pip Install Test"
echo "========================================"
echo ""

# Step 1: Create fresh venv
test_step "Create venv" bash -c "rm -rf $VENV_DIR && python3 -m venv $VENV_DIR"

# Step 2: Pip install
test_step "Pip install dockdesk" bash -c "source $VENV_DIR/bin/activate && pip install '$SCRIPT_DIR' --quiet"

# Step 3: CLI --help
test_step "dockdesk --help" bash -c "source $VENV_DIR/bin/activate && dockdesk --help | grep -q audit"

# Step 4: CLI --version
test_step "dockdesk --version" bash -c "source $VENV_DIR/bin/activate && dockdesk --version | grep -q dockdesk"

# Step 5: list-models
test_step "dockdesk list-models" bash -c "source $VENV_DIR/bin/activate && dockdesk list-models"

# Step 6: Clone test repo
test_step "Clone test repo" bash -c "rm -rf $CLONE_DIR && git clone --depth 1 $TEST_REPO $CLONE_DIR"

# Step 7: Run audit
test_step "dockdesk audit (10 files, fast)" bash -c "source $VENV_DIR/bin/activate && dockdesk audit --workspace $CLONE_DIR --skip-rag --max-files 10 --fast"

# Step 8: Verify report
test_step "Verify audit_report.md" bash -c "test -s $CLONE_DIR/audit_report.md"

# Step 9: Verify dashboard data
test_step "Verify dashboard_data.json" bash -c "test -s $CLONE_DIR/dashboard_data.json && python3 -c \"import json; d=json.load(open('$CLONE_DIR/dashboard_data.json')); assert len(d.get('latest_run_files',[])) > 0\""

# Step 10: python -m dockdesk
test_step "python -m dockdesk --help" bash -c "source $VENV_DIR/bin/activate && python -m dockdesk --help | grep -q audit"

# Cleanup
echo ""
echo "  Cleaning up..."
rm -rf "$VENV_DIR" "$CLONE_DIR"

# Summary
echo ""
echo "========================================"
PASSED=$((TOTAL - FAILED))
if [ "$FAILED" -eq 0 ]; then
    echo "  ALL $TOTAL TESTS PASSED"
    exit 0
else
    echo "  $FAILED/$TOTAL TEST(S) FAILED"
    exit 1
fi
