"""
DockDesk Git Hooks - Pre-push audit gates.

Installs/manages git pre-push hooks that run fast-mode audits
and block pushes when HIGH risk findings are detected.

Usage:
    dockdesk hooks install [--workspace .]
    dockdesk hooks uninstall [--workspace .]
    dockdesk hooks status [--workspace .]
"""

import os
import sys
import stat
from pathlib import Path
from typing import Optional
from rich.console import Console

console = Console(highlight=False)

HOOK_MARKER = "# DOCKDESK_MANAGED_HOOK"

PRE_PUSH_SCRIPT_UNIX = '''#!/bin/sh
{marker}
# DockDesk Pre-Push Audit Gate
# Auto-installed by: dockdesk hooks install
# Runs a fast-mode audit and blocks push on HIGH risk findings.

echo "\\033[35m DockDesk pre-push audit running...\\033[0m"

"{python_executable}" -m dockdesk audit --workspace . --fast --turbo --format json 2>/dev/null
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "\\033[31m DockDesk: Push BLOCKED - audit found HIGH risk issues.\\033[0m"
    echo "\\033[33m  Run 'dockdesk audit' for full details.\\033[0m"

    # Attempt Discord notification asynchronously
    "{python_executable}" -c "
from dockdesk.discord import DiscordNotifier
n = DiscordNotifier()
if n.enabled:
    n.post_push_blocked('Pre-push hook blocked a push due to HIGH risk findings.')
" 2>/dev/null &

    exit 1
fi

echo "\\033[32m DockDesk: Audit passed - push allowed.\\033[0m"
exit 0
'''

PRE_PUSH_SCRIPT_WINDOWS = '''#!/bin/sh
{marker}
# DockDesk Pre-Push Audit Gate (Windows)

echo "DockDesk pre-push audit running..."

"{python_executable}" -m dockdesk audit --workspace . --fast --turbo --format json 2>NUL
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "DockDesk: Push BLOCKED - audit found HIGH risk issues."
    echo "  Run 'dockdesk audit' for full details."

    # Attempt Discord notification asynchronously (Git Bash provides /bin/sh so & works)
    "{python_executable}" -c "
from dockdesk.discord import DiscordNotifier
n = DiscordNotifier()
if n.enabled:
    n.post_push_blocked('Pre-push hook blocked a push due to HIGH risk findings.')
" 2>NUL &

    exit 1
fi

echo "DockDesk: Audit passed - push allowed."
exit 0
'''


def _git_hooks_dir(workspace: str) -> Optional[Path]:
    """Find the .git/hooks directory for the workspace."""
    git_dir = Path(workspace) / ".git"
    if git_dir.is_dir():
        hooks_dir = git_dir / "hooks"
        hooks_dir.mkdir(exist_ok=True)
        return hooks_dir

    # Support git worktrees (where .git is a file pointing to the actual dir)
    if git_dir.is_file():
        try:
            content = git_dir.read_text().strip()
            if content.startswith("gitdir: "):
                actual_git = Path(workspace) / content[8:]
                hooks_dir = actual_git / "hooks"
                hooks_dir.mkdir(exist_ok=True)
                return hooks_dir
        except Exception:
            pass

    return None


def install_hooks(workspace: str) -> bool:
    """Install the DockDesk pre-push hook."""
    hooks_dir = _git_hooks_dir(workspace)
    if not hooks_dir:
        console.print("[red] Not a git repository. Cannot install hooks.[/red]")
        return False

    hook_path = hooks_dir / "pre-push"

    # Check for existing non-DockDesk hook
    if hook_path.exists():
        content = hook_path.read_text(encoding="utf-8", errors="ignore")
        if HOOK_MARKER not in content:
            console.print("[yellow] Existing pre-push hook found (not managed by DockDesk).[/yellow]")
            console.print("[yellow]  Backup at: pre-push.bak[/yellow]")
            backup = hooks_dir / "pre-push.bak"
            hook_path.rename(backup)

    script = PRE_PUSH_SCRIPT_WINDOWS if os.name == "nt" else PRE_PUSH_SCRIPT_UNIX
    script = script.replace("{marker}", HOOK_MARKER)
    python_exe = sys.executable.replace("\\", "/")
    script = script.replace("{python_executable}", python_exe)

    hook_path.write_text(script, encoding="utf-8")

    # Make executable (Unix)
    if os.name != "nt":
        hook_path.chmod(hook_path.stat().st_mode | stat.S_IEXEC)

    console.print(f"[green] Pre-push hook installed: {hook_path}[/green]")
    console.print("[dim]  Pushes will now run a fast-mode audit gate.[/dim]")
    return True


def uninstall_hooks(workspace: str) -> bool:
    """Remove DockDesk-managed hooks."""
    hooks_dir = _git_hooks_dir(workspace)
    if not hooks_dir:
        console.print("[red] Not a git repository.[/red]")
        return False

    hook_path = hooks_dir / "pre-push"
    if not hook_path.exists():
        console.print("[yellow]No pre-push hook found.[/yellow]")
        return False

    content = hook_path.read_text(encoding="utf-8", errors="ignore")
    if HOOK_MARKER not in content:
        console.print("[yellow]Pre-push hook exists but is not managed by DockDesk. Skipping.[/yellow]")
        return False

    hook_path.unlink()
    console.print("[green] DockDesk pre-push hook removed.[/green]")

    # Restore backup if exists
    backup = hooks_dir / "pre-push.bak"
    if backup.exists():
        backup.rename(hook_path)
        console.print("[dim]  Original pre-push hook restored from backup.[/dim]")

    return True


def hooks_status(workspace: str) -> dict:
    """Check hook installation status."""
    hooks_dir = _git_hooks_dir(workspace)
    result = {"installed": False, "managed": False, "path": None}

    if not hooks_dir:
        console.print("[yellow]Not a git repository.[/yellow]")
        return result

    hook_path = hooks_dir / "pre-push"
    if not hook_path.exists():
        console.print("[dim]No pre-push hook installed.[/dim]")
        return result

    content = hook_path.read_text(encoding="utf-8", errors="ignore")
    is_managed = HOOK_MARKER in content

    result["installed"] = True
    result["managed"] = is_managed
    result["path"] = str(hook_path)

    if is_managed:
        console.print(f"[green] DockDesk pre-push hook is active: {hook_path}[/green]")
    else:
        console.print(f"[yellow]Pre-push hook exists but is NOT managed by DockDesk: {hook_path}[/yellow]")

    return result
