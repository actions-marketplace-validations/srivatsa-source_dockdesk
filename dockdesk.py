#!/usr/bin/env python3
"""
DockDesk - Master CLI

Simple entry point to run audits, view dashboard, or manage models.

Usage:
    python dockdesk.py              # Interactive menu
    python dockdesk.py audit        # Run audit directly
    python dockdesk.py dashboard    # Open dashboard in browser
    python dockdesk.py models       # List available models
"""

import os
import sys
import subprocess
import shutil

WORKSPACE = os.path.dirname(os.path.abspath(__file__))
AUDITOR = os.path.join(WORKSPACE, "auditor_slm.py")
DASHBOARD_DIR = os.path.join(WORKSPACE, "dashboard")


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
║        🛡️  DockDesk - Semantic Auditor       ║
║     Code ↔ Documentation Sync Checker        ║
╚══════════════════════════════════════════════╝
""")


def print_status():
    """Print system status."""
    running, models = check_ollama()
    status = "🟢 Running" if running else "🔴 Not running"
    print(f"  Ollama:    {status}")
    if models:
        print(f"  Models:    {', '.join(models)}")
    else:
        print("  Models:    None found — run: ollama pull qwen2.5-coder:3b")
    
    history = os.path.join(WORKSPACE, "audit_history.jsonl")
    if os.path.exists(history):
        count = sum(1 for line in open(history) if '"run_metadata"' in line)
        print(f"  History:   {count} audit run(s)")
    else:
        print("  History:   No audits yet")
    print()


def run_audit(extra_args=None):
    """Run the DockDesk audit."""
    running, models = check_ollama()
    if not running:
        print("\n❌ Ollama is not running!")
        print("   Start it with:  ollama serve")
        print("   Then pull a model:  ollama pull qwen2.5-coder:3b")
        return

    cmd = [python_cmd(), AUDITOR, "--skip-rag"]
    if extra_args:
        cmd.extend(extra_args)

    print(f"\n🔍 Running audit...")
    print(f"   Command: {' '.join(cmd)}\n")
    subprocess.run(cmd, cwd=WORKSPACE)


def open_dashboard():
    """Export data and open the dashboard."""
    history = os.path.join(WORKSPACE, "audit_history.jsonl")
    public_dir = os.path.join(DASHBOARD_DIR, "public")
    data_file = os.path.join(public_dir, "dashboard_data.json")

    # Export audit data if history exists
    os.makedirs(public_dir, exist_ok=True)
    if os.path.exists(history):
        print("📊 Exporting audit data...")
        subprocess.run(
            [python_cmd(), AUDITOR, "dashboard", "--workspace", WORKSPACE, "--export", data_file],
            cwd=WORKSPACE,
            capture_output=True
        )
        print("   ✓ Data exported")
    else:
        print("⚠️  No audit history yet — dashboard will show sample data")

    # Check if node is available
    npx = shutil.which("npx")
    if not npx:
        print("\n❌ Node.js not found! Install from: https://nodejs.org")
        return

    # Install deps if needed
    node_modules = os.path.join(DASHBOARD_DIR, "node_modules")
    if not os.path.exists(node_modules):
        print("📦 Installing dashboard dependencies (first time only)...")
        subprocess.run(["npm", "install"], cwd=DASHBOARD_DIR, capture_output=True, shell=True)

    # Start Vite dev server
    print("🚀 Starting dashboard at http://localhost:3000")
    print("   Press Ctrl+C to stop\n")
    try:
        subprocess.run(["npx", "vite", "--port", "3000", "--open"], cwd=DASHBOARD_DIR, shell=True)
    except KeyboardInterrupt:
        print("\n\n✓ Dashboard stopped")


def list_models():
    """List available Ollama models."""
    subprocess.run([python_cmd(), AUDITOR, "list-models"], cwd=WORKSPACE)


def interactive_menu():
    """Show interactive menu."""
    print_banner()
    print_status()

    print("  Choose an option:\n")
    print("    [1]  🔍 Run Audit")
    print("    [2]  📊 Open Dashboard")
    print("    [3]  🤖 List Models")
    print("    [4]  ⚙️  Init Config")
    print("    [5]  ❌ Exit")
    print()

    try:
        choice = input("  Enter choice (1-5): ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\n")
        return

    if choice == "1":
        model = input("  Model (Enter for default qwen2.5-coder:3b): ").strip()
        fmt = input("  Format [md/json/sarif] (Enter for md): ").strip() or "md"
        verbose = input("  Verbose? [y/N]: ").strip().lower() == "y"

        args = ["--format", fmt]
        if model:
            args.extend(["--model", model])
        if verbose:
            args.append("--verbose")
        run_audit(args)

    elif choice == "2":
        open_dashboard()

    elif choice == "3":
        list_models()

    elif choice == "4":
        subprocess.run([python_cmd(), AUDITOR, "init", "--workspace", WORKSPACE], cwd=WORKSPACE)

    elif choice == "5":
        print("  Bye! 👋")
    else:
        print(f"  Unknown option: {choice}")


def main():
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "audit":
            run_audit(sys.argv[2:])
        elif cmd == "dashboard":
            open_dashboard()
        elif cmd == "models":
            list_models()
        elif cmd == "init":
            subprocess.run([python_cmd(), AUDITOR, "init", "--workspace", WORKSPACE], cwd=WORKSPACE)
        elif cmd in ("-h", "--help", "help"):
            print(__doc__)
        else:
            print(f"Unknown command: {cmd}")
            print("Use: audit, dashboard, models, init")
    else:
        interactive_menu()


if __name__ == "__main__":
    main()
