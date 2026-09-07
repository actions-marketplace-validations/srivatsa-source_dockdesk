#!/usr/bin/env python3
"""
DockDesk - Master CLI

Simple entry point to run audits, view dashboard, or manage models.

Usage:
    dockdesk audit /path/to/repo     # Audit a target repo
    dockdesk dashboard               # Open dashboard in browser
    dockdesk models                  # List available models
    dockdesk init                    # Create config file
    dockdesk hooks                   # Install pre-push hook
    dockdesk                         # Interactive menu
"""

import os
import sys
import subprocess
import shutil

# Resolve the directory where dockdesk is installed (for finding dashboard assets)
_INSTALL_DIR = os.path.dirname(os.path.abspath(__file__))
DASHBOARD_DIR = os.path.join(_INSTALL_DIR, "dashboard")


def _resolve_workspace(workspace_arg=None):
    """Resolve the target workspace path. Defaults to CWD, not install dir."""
    if workspace_arg:
        return os.path.abspath(workspace_arg)
    return os.getcwd()


def _find_auditor():
    """Find auditor_slm.py — either next to this file or via the dockdesk package."""
    # First try: auditor_slm.py next to this script (dev / clone mode)
    local = os.path.join(_INSTALL_DIR, "auditor_slm.py")
    if os.path.exists(local):
        return [sys.executable, local]
    # Fallback: use the installed package entry point
    return [sys.executable, "-m", "dockdesk.cli"]


def python_cmd():
    """Get the correct python command for this system."""
    # Use the same Python that's running this script
    return sys.executable


def check_ollama():
    """Check if Ollama is running and return available models."""
    try:
        import requests
        host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        r = requests.get(f"{host}/api/tags", timeout=3)
        if r.ok:
            models = [m["name"] for m in r.json().get("models", [])]
            return True, models
    except Exception:
        pass
    return False, []


def print_banner():
    """Print the DockDesk banner."""
    print("""
╔══════════════════════════════════════════════╗
║    🛡️  DockDesk - Dual-Model Auditor          ║
║   Qwen Coder + DeepSeek-R1 Reasoning          ║
╚══════════════════════════════════════════════╝
""")


def print_status(workspace=None):
    """Print system status."""
    workspace = _resolve_workspace(workspace)
    running, models = check_ollama()
    status = "Running" if running else "Not running"
    print(f"  Ollama:    {status}")
    if models:
        print(f"  Models:    {', '.join(models)}")
    else:
        print("  Models:    None found — run: ollama pull qwen2.5-coder:7b")
    
    # Check for Discord webhook
    webhook = os.environ.get("DOCKDESK_DISCORD_WEBHOOK", "")
    if webhook:
        print(f"  Discord:   Webhook configured")
    else:
        print(f"  Discord:   Not configured (set DOCKDESK_DISCORD_WEBHOOK)")
    
    history = os.path.join(workspace, "audit_history.jsonl")
    if os.path.exists(history):
        count = sum(1 for line in open(history) if '"run_metadata"' in line)
        print(f"  History:   {count} audit run(s)")
    else:
        print("  History:   No audits yet")
    print(f"  Target:    {workspace}")
    print()


def run_audit(extra_args=None, workspace=None):
    """Run the DockDesk audit."""
    workspace = _resolve_workspace(workspace)
    running, models = check_ollama()
    if not running:
        print("\nOllama is not running!")
        print("   Start it with:  ollama serve")
        print("   Then pull a model:  ollama pull qwen2.5-coder:7b")
        return

    cmd = _find_auditor() + ["--workspace", workspace, "--skip-rag"]
    
    # Always add reasoning model
    reasoning = os.environ.get("DOCKDESK_REASONING_MODEL", "deepseek-r1:1.5b")
    cmd.extend(["--reasoning-model", reasoning])
    
    # Add discord webhook if configured
    webhook = os.environ.get("DOCKDESK_DISCORD_WEBHOOK", "")
    if webhook:
        cmd.extend(["--discord-webhook", webhook])
    
    if extra_args:
        cmd.extend(extra_args)

    print(f"\nRunning audit on {workspace}...")
    print(f"   Command: {' '.join(cmd)}\n")
    subprocess.run(cmd)


def open_dashboard(workspace=None):
    """Export data and open the dashboard."""
    workspace = _resolve_workspace(workspace)
    history = os.path.join(workspace, "audit_history.jsonl")
    public_dir = os.path.join(DASHBOARD_DIR, "public")
    data_file = os.path.join(public_dir, "dashboard_data.json")

    # Export audit data if history exists
    os.makedirs(public_dir, exist_ok=True)
    if os.path.exists(history):
        print("Exporting audit data...")
        cmd = _find_auditor() + ["dashboard", "--workspace", workspace, "--export", data_file]
        subprocess.run(cmd, capture_output=True)
        print("   ✓ Data exported")
    else:
        print("No audit history yet - dashboard will show sample data")

    # Check if node is available
    npx = shutil.which("npx")
    if not npx:
        print("\nNode.js not found! Install from: https://nodejs.org")
        return

    # Install deps if needed
    node_modules = os.path.join(DASHBOARD_DIR, "node_modules")
    if not os.path.exists(node_modules):
        print("Installing dashboard dependencies (first time only)...")
        subprocess.run(["npm", "install"], cwd=DASHBOARD_DIR, capture_output=True, shell=True)

    # Start Vite dev server
    print("Starting dashboard at http://localhost:3000")
    print("   Press Ctrl+C to stop\n")
    try:
        subprocess.run(["npx", "vite", "--port", "3000", "--open"], cwd=DASHBOARD_DIR, shell=True)
    except KeyboardInterrupt:
        print("\n\n✓ Dashboard stopped")


def list_models():
    """List available Ollama models."""
    subprocess.run(_find_auditor() + ["list-models"])


def install_pre_push_hook(workspace=None):
    """Install the DockDesk pre-push Git hook in the target workspace."""
    workspace = _resolve_workspace(workspace)
    git_dir = os.path.join(workspace, ".git")
    if not os.path.isdir(git_dir):
        print("  Not a Git repository. Run 'git init' first.")
        return

    hooks_dir = os.path.join(git_dir, "hooks")
    os.makedirs(hooks_dir, exist_ok=True)
    hook_path = os.path.join(hooks_dir, "pre-push")

    # Use the installed CLI command if available, otherwise fall back to python -m
    dockdesk_cmd = shutil.which("dockdesk")
    if dockdesk_cmd:
        audit_cmd = f'dockdesk audit --workspace "$(git rev-parse --show-toplevel)"'
    else:
        audit_cmd = f'"{sys.executable}" -m dockdesk.cli audit --workspace "$(git rev-parse --show-toplevel)"'

    hook_script = f"""#!/bin/sh
# DockDesk Pre-Push Guard
# Runs dual-model audit and blocks pushes with HIGH risk findings.

echo "🛡️  DockDesk Pre-Push Audit..."

REASONING_MODEL="${{DOCKDESK_REASONING_MODEL:-deepseek-r1:1.5b}}"
CODE_MODEL="${{DOCKDESK_MODEL:-qwen2.5-coder:7b}}"
DISCORD_WEBHOOK="${{DOCKDESK_DISCORD_WEBHOOK:-}}"

EXTRA_ARGS=""
if [ -n "$DISCORD_WEBHOOK" ]; then
    EXTRA_ARGS="$EXTRA_ARGS --discord-webhook $DISCORD_WEBHOOK"
fi

{audit_cmd} \\
    --model "$CODE_MODEL" \\
    --reasoning-model "$REASONING_MODEL" \\
    --skip-rag \\
    --ci \\
    --fail-on-risk HIGH \\
    $EXTRA_ARGS

EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "Push BLOCKED: HIGH risk findings detected."
    echo "   Fix the issues or run: git push --no-verify"
    exit 1
fi

echo "Push approved by DockDesk."
exit 0
"""

    with open(hook_path, "w", newline="\n") as f:
        f.write(hook_script)

    # Make executable on Unix
    try:
        os.chmod(hook_path, 0o755)
    except Exception:
        pass

    print(f"  ✓ Pre-push hook installed: {hook_path}")
    print(f"  Pushes will be audited with Qwen + DeepSeek-R1 before pushing.")
    print(f"  To bypass: git push --no-verify")


def interactive_menu():
    """Show interactive menu."""
    print_banner()

    # Ask for target workspace
    default_ws = os.getcwd()
    ws_input = input(f"  Target workspace [{default_ws}]: ").strip()
    workspace = ws_input if ws_input else default_ws
    workspace = os.path.abspath(workspace)
    print()

    print_status(workspace)

    print("  Choose an option:\n")
    print("    [1]  Run Audit")
    print("    [2]  Open Dashboard")
    print("    [3]  🤖 List Models")
    print("    [4]  ⚙️  Init Config")
    print("    [5]  🔗 Set Discord Webhook")
    print("    [6]  🪝 Install Pre-Push Hook")
    print("    [7]  Exit")
    print()

    try:
        choice = input("  Enter choice (1-7): ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\n")
        return

    if choice == "1":
        model = input("  Code model (Enter for default qwen2.5-coder:7b): ").strip()
        fmt = input("  Format [md/json/sarif] (Enter for md): ").strip() or "md"
        verbose = input("  Verbose? [y/N]: ").strip().lower() == "y"

        args = ["--format", fmt]
        if model:
            args.extend(["--model", model])
        if verbose:
            args.append("--verbose")
        run_audit(args, workspace)

    elif choice == "2":
        open_dashboard(workspace)

    elif choice == "3":
        list_models()

    elif choice == "4":
        cmd = _find_auditor() + ["init", "--workspace", workspace]
        subprocess.run(cmd)

    elif choice == "5":
        webhook = input("  Discord Webhook URL: ").strip()
        if webhook:
            os.environ["DOCKDESK_DISCORD_WEBHOOK"] = webhook
            print(f"  ✓ Webhook set for this session.")
            print(f"  To persist, add to your shell: export DOCKDESK_DISCORD_WEBHOOK={webhook}")
        else:
            print("  No URL provided.")

    elif choice == "6":
        install_pre_push_hook(workspace)

    elif choice == "7":
        print("  Bye! 👋")
    else:
        print(f"  Unknown option: {choice}")


def main():
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()

        # Extract --workspace from remaining args if present
        remaining = sys.argv[2:]
        workspace = None
        filtered = []
        i = 0
        while i < len(remaining):
            if remaining[i] in ("--workspace", "-w") and i + 1 < len(remaining):
                workspace = remaining[i + 1]
                i += 2
            else:
                filtered.append(remaining[i])
                i += 1

        if cmd == "audit":
            run_audit(filtered, workspace)
        elif cmd == "dashboard":
            open_dashboard(workspace)
        elif cmd == "models":
            list_models()
        elif cmd == "init":
            ws = _resolve_workspace(workspace)
            subprocess.run(_find_auditor() + ["init", "--workspace", ws])
        elif cmd == "hooks":
            install_pre_push_hook(workspace)
        elif cmd in ("-h", "--help", "help"):
            print(__doc__)
        else:
            print(f"Unknown command: {cmd}")
            print("Use: audit, dashboard, models, init, hooks")
    else:
        interactive_menu()


if __name__ == "__main__":
    main()
