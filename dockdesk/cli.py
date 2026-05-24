#!/usr/bin/env python3
"""
DockDesk CLI - pip-installable entry point.

This module provides the `dockdesk` console command when installed via pip.
It re-exports all functionality from auditor_slm.py for backward compatibility.

Usage:
    dockdesk audit /path/to/repo          # Audit a target repo
    dockdesk audit --auto-tune --fix      # Auto-model + fix
    dockdesk list-models                  # Show available models
    dockdesk init --workspace /path       # Create config file
    dockdesk dashboard --workspace /path  # View audit stats
    dockdesk setup                        # Install Ollama + pull models
"""

import argparse
import sys
import os
import json
import time
import tempfile
import shutil
import subprocess
import re
import atexit
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.prompt import Prompt

console = Console(highlight=False)

def _print_loading(skip: bool = False, version: str = ""):
    from dockdesk.ui import print_logo, print_init_spinners
    print_init_spinners(skip=skip, version=version)


# ── Git URL / remote repo support ──

_GIT_URL_PATTERN = re.compile(
    r"^(https?://|git@|ssh://)", re.IGNORECASE
)

_temp_clone_dirs: list[str] = []


def _cleanup_temp_clones():
    """Remove any temporary clone directories on exit."""
    for d in _temp_clone_dirs:
        try:
            shutil.rmtree(d, ignore_errors=True)
        except Exception:
            pass


atexit.register(_cleanup_temp_clones)


# ── Interactive workspace picker ───────────────────────────────────────────────

_PROJECT_MARKERS = {
    ".git",
    "pyproject.toml",
    "package.json",
    "pom.xml",
    "build.gradle",
    "requirements.txt",
    "setup.py",
    "Cargo.toml",
    "go.mod",
    "*.sln",
}

_SOURCE_SUFFIXES = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".cs", ".go", ".rs", ".cpp", ".c", ".h"
}


def _looks_like_project(path: Path) -> tuple[bool, str]:
    """Heuristic to decide whether a folder is an auditable project root."""
    if not path.is_dir():
        return False, ""

    for marker in _PROJECT_MARKERS:
        if "*" in marker:
            if list(path.glob(marker)):
                return True, f"marker: {marker}"
        elif (path / marker).exists():
            return True, f"marker: {marker}"

    # Fallback: has enough source files and basic project metadata.
    src_dirs = [path, path / "src", path / "app", path / "lib"]
    source_count = 0
    for d in src_dirs:
        if not d.exists() or not d.is_dir():
            continue
        try:
            for child in d.iterdir():
                if child.is_file() and child.suffix.lower() in _SOURCE_SUFFIXES:
                    source_count += 1
                    if source_count >= 8:
                        has_meta = any(
                            (path / name).exists()
                            for name in ("README.md", "README", "LICENSE", ".gitignore")
                        )
                        if has_meta:
                            return True, "marker: source files"
        except (PermissionError, OSError):
            continue

    return False, ""


def _discover_projects(base_dir: Path, max_depth: int = 3, limit: int = 40) -> list[tuple[Path, str]]:
    """Discover likely project folders under base_dir with shallow recursion."""
    projects: list[tuple[Path, str]] = []
    seen: set[str] = set()

    def walk(cur: Path, depth: int) -> None:
        if len(projects) >= limit or depth > max_depth:
            return
        try:
            entries = list(cur.iterdir())
        except (PermissionError, OSError):
            return

        is_proj, reason = _looks_like_project(cur)
        cur_key = str(cur.resolve()).lower()
        if is_proj and cur_key not in seen:
            # Avoid showing nested source-only folders when parent already has stronger markers.
            ancestor_has_project = any(
                str(parent.resolve()).lower() in seen
                for parent in cur.parents
                if parent.resolve() != base_dir.resolve()
            )

            if ancestor_has_project and reason == "marker: source files":
                is_proj = False

        if is_proj and cur_key not in seen:
            projects.append((cur, reason))
            seen.add(cur_key)

        for entry in entries:
            if len(projects) >= limit:
                return
            if not entry.is_dir():
                continue
            if entry.name.startswith("."):
                continue
            if entry.name in {"node_modules", "__pycache__", ".venv", "venv", "dist", "build", "target"}:
                continue
            walk(entry, depth + 1)

    walk(base_dir, 0)
    projects.sort(key=lambda p: str(p[0]).lower())
    return projects


def _render_project_table(projects: list[tuple[Path, str]], base_dir: Path) -> None:
    table = Table(title="[bold #FF1493]Auditable Local Projects[/bold #FF1493]", show_lines=True)
    table.add_column("#", style="bold #DA70D6", justify="right", width=4)
    table.add_column("Project Folder", style="#FF00FF", overflow="fold")
    table.add_column("Signal", style="#FF69B4")

    for i, (path, reason) in enumerate(projects, start=1):
        try:
            display = str(path.relative_to(base_dir))
        except ValueError:
            display = str(path)
        table.add_row(str(i), display, reason)

    console.print(table)


def _browse_for_workspace(start_dir: Path, *, enter_on_select: bool = True) -> Path | None:
    """Phenomenal interactive folder browser using Rich Live and keyboard navigation."""
    from rich.live import Live
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    import time
    
    current = start_dir.resolve()
    selected_idx = 0
    
    # ── Cross-Platform Non-Blocking Key Reader ──
    if os.name == "nt":
        import msvcrt
        def read_key() -> str:
            if msvcrt.kbhit():
                ch = msvcrt.getch()
                if ch in (b'\x00', b'\xe0'):
                    ch2 = msvcrt.getch()
                    if ch2 == b'H': return 'up'
                    if ch2 == b'P': return 'down'
                    return ''
                if ch == b'\r': return 'enter'
                if ch == b'\n': return 'shift-enter'  # Shift+Enter registers as \n in Windows consoles
                if ch == b'\x1b': return 'esc'
                try:
                    c = ch.decode('utf-8', errors='ignore')
                except Exception:
                    return ''
                return c
            return ''
    else:
        import tty, termios, select
        _old_settings = None
        def _init_tty():
            nonlocal _old_settings
            _old_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
        def _restore_tty():
            if _old_settings:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, _old_settings)

        def read_key() -> str:
            if select.select([sys.stdin], [], [], 0.05)[0]:
                ch = sys.stdin.read(1)
                if ch == '\x1b':
                    if select.select([sys.stdin], [], [], 0.02)[0]:
                        ch2 = sys.stdin.read(1)
                        if ch2 == '[':
                            ch3 = sys.stdin.read(1)
                            if ch3 == 'A': return 'up'
                            if ch3 == 'B': return 'down'
                    return 'esc'
                if ch in ('\r', '\n'):
                    return 'enter'
                return ch
            return ''

    if os.name != "nt":
        _init_tty()

    try:
        dirs: list[Path] = []
        
        def refresh_dirs():
            nonlocal dirs, selected_idx
            try:
                all_entries = sorted(
                    [p for p in current.iterdir() if not p.name.startswith(".")],
                    key=lambda p: (not p.is_dir(), p.name.lower())
                )
                dirs = all_entries
            except (PermissionError, OSError):
                dirs = []
            selected_idx = min(selected_idx, max(0, len(dirs)))

        refresh_dirs()

        def make_panel() -> Panel:
            table = Table(box=None, show_header=False, expand=True)
            table.add_column("Pointer", width=2, style="bold #FF1493")
            table.add_column("Type", width=8)
            table.add_column("Name", style="#FF69B4")

            parent_selected = (selected_idx == 0)
            ptr = "▸" if parent_selected else " "
            p_style = "bold #FF1493" if parent_selected else "dim"
            row_style = "on #13132B" if parent_selected else ""
            table.add_row(
                Text(ptr, style=p_style),
                Text("[DIR]", style="bold #8A2BE2"),
                Text(".. (parent folder)", style="bold #DA70D6" if parent_selected else "#DA70D6"),
                style=row_style
            )

            for i, p in enumerate(dirs):
                idx = i + 1
                is_selected = (selected_idx == idx)
                ptr = "▸" if is_selected else " "
                p_style = "bold #FF1493" if is_selected else "dim"
                row_style = "on #13132B" if is_selected else ""
                
                ptype = "[DIR]" if p.is_dir() else "[FILE]"
                tstyle = "bold #8A2BE2" if p.is_dir() else "dim #DA70D6"
                
                table.add_row(
                    Text(ptr, style=p_style),
                    Text(ptype, style=tstyle),
                    Text(p.name, style="bold #FF00FF" if is_selected else "#FF69B4"),
                    style=row_style
                )

            return Panel(
                table,
                title=Text(f" 📂 Folder & File Explorer ── {current} ", style="bold #FF1493"),
                subtitle=Text(" [↑/↓/j/k]: Navigate  ∣  [Enter]: Open  ∣  [Shift+Enter / 's']: Start Audit  ∣  [q]: Cancel ", style="dim #DA70D6"),
                border_style="#8A2BE2",
                padding=(1, 2)
            )

        with Live(make_panel(), screen=True, refresh_per_second=15) as live:
            while True:
                key = read_key()
                if not key:
                    time.sleep(0.02)
                    continue

                if key == 'q' or key == 'esc':
                    return None
                
                elif key in ('j', 'down'):
                    selected_idx = min(selected_idx + 1, len(dirs))
                
                elif key in ('k', 'up'):
                    selected_idx = max(selected_idx - 1, 0)
                
                elif key in ('s', 'S', 'shift-enter'):
                    if selected_idx == 0:
                        return current
                    else:
                        return dirs[selected_idx - 1]

                elif key == 'enter':
                    if selected_idx == 0:
                        current = current.parent
                        selected_idx = 0
                        refresh_dirs()
                    else:
                        target = dirs[selected_idx - 1]
                        if target.is_dir():
                            current = target
                            selected_idx = 0
                            refresh_dirs()
                        else:
                            return target
                
                live.update(make_panel())
                time.sleep(0.01)

    finally:
        if os.name != "nt":
            _restore_tty()


def _chat_interface() -> None:
    """Main conversational flow for users running dockdesk with no args."""
    from dockdesk import __version__ as _ver
    from dockdesk.chat import parse_intent
    from dockdesk.ollama_pool import OllamaPool
    import logging

    # Suppress httpx logs for cleaner chat
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Show startup animation when entering interactive CLI.
    _print_loading(skip=False, version=_ver)
    workspace = str(Path.cwd().resolve())

    console.print(Panel(
        f"[bold #FF1493]DockDesk Neural Chat Interface[/bold #FF1493]\n"
        f"[white]Current Workspace:[/white] [#FF69B4]{workspace}[/#FF69B4]\n"
        "[dim]Tell me what you want to do (e.g., 'run audit', 'show dashboard stats', 'change workspace to /path'). Type 'exit' to quit.[/dim]",
        border_style="#8A2BE2"
    ))

    pool = OllamaPool([ "http://localhost:11434" ], run_health_check=False)

    while True:
        try:
            choice = Prompt.ask(f"\n[#FF00FF]dockdesk[/] [dim]({Path(workspace).name})[/] ❯").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Session closed.[/dim]")
            return

        if not choice:
            continue

        intent = parse_intent(choice, pool=pool, workspace_path=workspace)
        action = intent.get("action", "unknown")

        if action == "exit":
            console.print("[dim]Session closed.[/dim]")
            return
        elif action == "audit":
            target = intent.get("workspace", "current")
            args_obj = intent.get("args", {})
            include_from_args = args_obj.get("include")
            
            # Always resolve target first to support auditing entire nested folders properly
            selected = _prompt_audit_target(current_workspace=workspace, suggested_target=target, skip_prompts=bool(include_from_args or any(k in args_obj for k in ["fast_mode", "turbo", "model"])))
            if selected is None:
                continue
            
            target_ws, final_include = selected
            
            # If the user specified explicit options via NLP, we skip the options prompts
            if include_from_args or any(k in args_obj for k in ["fast_mode", "turbo", "model"]):
                # Use include_from_args if NLP provided it, else fallback to what target resolution gave
                include_pattern = include_from_args if include_from_args else final_include
                
                # Fetch base config
                from dockdesk.config import build_config
                try:
                    base_config = build_config(target_ws)
                    default_model = base_config.model
                    default_reasoning = base_config.reasoning_model
                except Exception:
                    default_model = "qwen2.5-coder:3b"
                    default_reasoning = "deepseek-r1:1.5b"

                is_auto_tune = args_obj.get("auto_tune", False)
                opts = argparse.Namespace(
                    workspace=target_ws,
                    model=None if is_auto_tune else args_obj.get("model", default_model),
                    detect_model=None,
                    fix_model=None,
                    reasoning_model=args_obj.get("reasoning_model", default_reasoning),
                    discord_webhook=None,
                    auto_tune=is_auto_tune,
                    fix=args_obj.get("fix", False),
                    fix_code=False,
                    ci=False,
                    verbose=False,
                    format=args_obj.get("format", "md"),
                    output=None,
                    fail_on_risk="HIGH",
                    skip_rag=args_obj.get("skip_rag", False),
                    max_files=None,
                    max_file_size=None,
                    include=include_pattern,
                    exclude=None,
                    workers=None,
                    ollama_urls=None,
                    fast=args_obj.get("fast_mode", False),
                    batch_size=None,
                    clear_cache=None,
                    no_gitignore=False,
                    turbo=args_obj.get("turbo", False),
                    keep_clone=False,
                    rules=None,
                    force_full_scan=None,
                    rotate_models=False,
                    _from_chat=True
                )
                
                console.print("[green][+] NLP parsed options automatically. Starting audit...[/green]")
                run_audit(opts)
            else:
                selected = _prompt_audit_target(current_workspace=workspace, suggested_target=target)
                if selected is None:
                    continue

                target_ws, include_pattern = selected
                opts = _interactive_audit_options(target_ws, include_pattern=include_pattern)
                if opts is not None:
                    opts._from_chat = True
                    run_audit(opts)
        elif action == "dashboard":
            section = intent.get("section", "summary")
            dashboard_cmd(argparse.Namespace(workspace=workspace, export=None, section=section, open=False))
        elif action == "open_react_dashboard":
            open_react_dashboard_cmd(argparse.Namespace(workspace=workspace))
        elif action == "change_workspace":
            path = intent.get("path", "browse")
            if path == "browse":
                picked = _browse_for_workspace(Path(workspace), enter_on_select=True)
                if picked:
                    workspace = str(picked.resolve())
            else:
                cand = Path(path).expanduser().resolve()
                if cand.exists() and cand.is_dir():
                    workspace = str(cand)
                    console.print(f"[green]Workspace changed to: {workspace}[/green]")
                else:
                    console.print(f"[bold red][-] Invalid folder path: {path}[/bold red]")
        elif action == "list_models":
            list_models_cmd(argparse.Namespace())
        elif action == "init_config":
            init_config_cmd(argparse.Namespace(workspace=workspace, force=False))
        elif action == "open_tui":
            from dockdesk.tui import launch_tui
            launch_tui(workspace)
        elif action == "hooks":
            sub = intent.get("sub_action", "status")
            from dockdesk.hooks import install_hooks, uninstall_hooks, hooks_status
            if sub == "install":
                install_hooks(workspace)
            elif sub == "uninstall":
                uninstall_hooks(workspace)
            else:
                hooks_status(workspace)
        else:
            msg = intent.get("message", "I didn't quite get that. Try 'run audit', 'show dashboard', or 'list models'.")
            console.print(f"[yellow]{msg}[/yellow]")


def _prompt_bool(label: str, default: bool = False) -> bool:
    """Prompt for yes/no using y/n with sensible defaults."""
    d = "y" if default else "n"
    value = Prompt.ask(label, default=d).strip().lower()
    return value in {"y", "yes", "true", "1"}


def _prompt_audit_target(current_workspace: str, suggested_target: str = "current", skip_prompts: bool = False) -> tuple[str, str | None] | None:
    """Ask and validate audit target path (file or folder) before starting an audit.

    Returns:
        (workspace_dir, include_pattern_if_file)
    """

    current = Path(current_workspace).expanduser().resolve()

    def _resolve_user_path(raw: str) -> list[Path]:
        raw = raw.strip().strip('"').strip("'").strip("`")
        raw = os.path.expandvars(raw)
        raw_path = Path(raw).expanduser()
        looks_like_path = any(sep in raw for sep in ("\\", "/")) or raw_path.drive != "" or raw.startswith(".")
        
        # 1. Exact Absolute
        if raw_path.is_absolute() and raw_path.exists():
            return [raw_path.resolve()]
        
        # 2. Exact Relative
        rel_cand = (current / raw_path).resolve()
        if rel_cand.exists():
            return [rel_cand]

        # If the user pasted a path-like value, do not invent fuzzy matches.
        if looks_like_path:
            return []
        
        # 3. Unbreakable Local Fuzzy & Substring Match
        import difflib
        matches = []
        ignored_dirs = {".git", "node_modules", ".venv", ".dockdesk_cache", "dist", "build", "__pycache__"}
        
        try:
            for root, dirs, files in os.walk(current):
                # Filter in-place
                dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith(".")]
                
                rel_depth = len(Path(root).relative_to(current).parts)
                if rel_depth > 3:
                    dirs[:] = []
                    continue
                
                # Scan files
                for f in files:
                    if raw.lower() in f.lower():
                        matches.append((1.0 if raw.lower() == f.lower() else 0.7, Path(root) / f))
                
                # Scan directories
                for d in dirs:
                    d_path = Path(root) / d
                    d_name = d.lower()
                    query = raw.lower()
                    
                    score = 0.0
                    if query == d_name:
                        score = 1.0
                    elif query in d_name:
                        score = 0.9 - (len(d_name) - len(query)) * 0.01
                    else:
                        score = difflib.SequenceMatcher(None, query, d_name).ratio()
                        
                    if score > 0.5:
                        # Project marker boost
                        try:
                            markers = ["pyproject.toml", "package.json", "Cargo.toml", ".git", "requirements.txt"]
                            if any(os.path.exists(os.path.join(d_path, m)) for m in markers):
                                score += 0.15
                        except Exception:
                            pass
                        matches.append((score, d_path))
        except Exception:
            pass
            
        matches.sort(key=lambda x: x[0], reverse=True)
        return [m[1] for m in matches[:5]]

    def _select_from_matches(matches: list[Path], raw: str) -> Path | None:
        if not matches:
            return None
        if len(matches) == 1 or skip_prompts:
            if not skip_prompts:
                console.print(f"[green]🤖 I found exactly what you meant:[/green] {matches[0]}")
            return matches[0]

        console.print(f"\n[green]🤖 I found these as matches for '{raw}', which one do you want to audit?[/green]")
        for idx, match in enumerate(matches, 1):
            console.print(f"[#DA70D6]{idx}[/#DA70D6] [#FF69B4]{match}[/#FF69B4]")
            
        while True:
            choice = Prompt.ask(f"[#FF00FF]Select a target (1-{len(matches)}) or 'q' to cancel[/#FF00FF]").strip()
            if choice.lower() == 'q':
                return None
            if choice.isdigit():
                idx = int(choice)
                if 1 <= idx <= len(matches):
                    return matches[idx - 1]
            console.print("[yellow][!] Invalid choice.[/yellow]")

    # Check the initial suggestion first. If successfully resolved & chosen, skip the default prompt entirely.
    if suggested_target and suggested_target != "current":
        matches = _resolve_user_path(suggested_target)
        target = _select_from_matches(matches, suggested_target)
        if target:
            if target.is_file():
                ws = target.parent.resolve()
                include = target.name
                if not skip_prompts:
                    console.print(f"[green]🤖 Auditing individual file:[/green] {target}")
                return str(ws), include

            if target.is_dir():
                console.print(f"[green]🤖 Auditing folder:[/green] {target}")
                return str(target.resolve()), None
    elif skip_prompts:
        return str(current), None

    console.print(Panel(
        "[bold #FF1493]Audit Target[/bold #FF1493]\n"
        "[dim]Choose what to audit first. You can provide a file or folder path.\n"
        "Use '.' for current workspace, 'b' to browse folders, or 'q' to cancel.[/dim]",
        border_style="#8A2BE2",
    ))

    while True:
        raw = Prompt.ask("[#DA70D6]Path to audit (file/folder)[/#DA70D6]", default=".").strip()

        if raw.lower() == "q":
            return None
        if raw.lower() == "b":
            picked = _browse_for_workspace(current, enter_on_select=False)
            if not picked:
                continue
            return str(picked.resolve()), None
        if raw == ".":
            return str(current), None

        matches = _resolve_user_path(raw)
        target = _select_from_matches(matches, raw)
        
        if not target:
            console.print("[yellow]🤖 I couldn't find a good match for that. Let's browse manually.[/yellow]")
            picked = _browse_for_workspace(current, enter_on_select=False)
            if not picked:
                continue
            return str(picked.resolve()), None

        if not target.exists():
            console.print(f"[bold red]🤖 I couldn't find the path: {target}[/bold red]")
            continue

        if target.is_file():
            ws = target.parent.resolve()
            include = target.name
            console.print(f"[green]🤖 Auditing individual file:[/green] {target}")
            return str(ws), include

        if target.is_dir():
            console.print(f"[green]🤖 Auditing folder:[/green] {target}")
            return str(target.resolve()), None

        console.print("[yellow][!] Unsupported target type. Choose a file or folder.[/yellow]")


def _interactive_audit_options(workspace: str, include_pattern: str | None = None) -> argparse.Namespace | None:
    """Collect quick audit options from interactive mode."""
    from dockdesk.config import build_config
    try:
        base_config = build_config(workspace)
        default_model = base_config.model
        default_reasoning_model = base_config.reasoning_model
        default_out_format = base_config.output_format.value
        default_auto_tune = getattr(base_config, 'auto_tune', False)
        default_skip_rag = getattr(base_config, 'skip_rag', False)
        default_fast_mode = getattr(base_config, 'fast_mode', False)
        default_rotate_models = getattr(base_config, 'rotate_models', False)
        default_turbo = getattr(base_config, 'turbo', False)
    except Exception:
        default_model = "qwen2.5-coder:3b"
        default_reasoning_model = "deepseek-r1:1.5b"
        default_out_format = "md"
        default_auto_tune = False
        default_skip_rag = False
        default_fast_mode = False
        default_rotate_models = False
        default_turbo = False

    console.print(Panel(
        "[bold #FF1493]Quick Audit Options[/bold #FF1493]\n"
        "[dim]Press Enter to accept standard settings (Fast, Auto-tuned, Cache enabled),\n"
        "or type 'c' to customize options manually.[/dim]",
        border_style="#8A2BE2"
    ))

    choice = Prompt.ask("[#DA70D6]Use standard recommended settings? (Y/c)[/#DA70D6]", default="y").strip().lower()
    if choice == 'q':
        return None
    if choice != 'c':
        # Fast-track path: return argparse namespace with recommended defaults
        return argparse.Namespace(
            workspace=workspace,
            model=None,
            detect_model=None,
            fix_model=None,
            reasoning_model=default_reasoning_model,
            discord_webhook=None,
            auto_tune=True,
            fix=False,
            fix_code=False,
            ci=False,
            verbose=False,
            format=default_out_format,
            output=None,
            fail_on_risk="HIGH",
            skip_rag=True,
            max_files=None,
            max_file_size=None,
            include=include_pattern,
            exclude=None,
            workers=None,
            ollama_urls=None,
            fast=True,
            batch_size=None,
            clear_cache=None,
            no_gitignore=False,
            turbo=True,
            keep_clone=False,
            rules=None,
            force_full_scan=None,
            rotate_models=False,
        )

    model = Prompt.ask("[#DA70D6]Code model[/#DA70D6]", default=default_model).strip()
    if model.lower() == "q":
        return None

    auto_tune = _prompt_bool("[#DA70D6]Auto-tune model by LOC?[/#DA70D6]", default=default_auto_tune)
    reasoning_model = Prompt.ask("[#DA70D6]Reasoning model[/#DA70D6]", default=default_reasoning_model).strip()
    out_format = Prompt.ask("[#DA70D6]Output format (md/json/sarif)[/#DA70D6]", default=default_out_format).strip().lower()
    if out_format not in {"md", "json", "sarif"}:
        console.print("[yellow][!] Invalid format, using md.[/yellow]")
        out_format = "md"

    skip_rag = _prompt_bool("[#DA70D6]Skip RAG for speed?[/#DA70D6]", default=default_skip_rag)
    fast_mode = _prompt_bool("[#DA70D6]Enable fast mode?[/#DA70D6]", default=default_fast_mode)
    rotate_models = _prompt_bool("[#DA70D6]Rotate code models per file?[/#DA70D6]", default=default_rotate_models)
    turbo = _prompt_bool("[#DA70D6]Enable turbo mode?[/#DA70D6]", default=default_turbo)
    apply_fixes = _prompt_bool("[#DA70D6]Apply documentation fixes?[/#DA70D6]", default=False)
    fix_code = _prompt_bool("[#DA70D6]Also allow code fixes?[/#DA70D6]", default=False) if apply_fixes else False
    verbose = _prompt_bool("[#DA70D6]Verbose output?[/#DA70D6]", default=False)

    save_config = Prompt.ask("[#DA70D6]Save these settings to dockdesk.yml? (y/n)[/#DA70D6]", default="y").strip().lower()
    if save_config == 'y':
        config_path = os.path.join(workspace, "dockdesk.yml")
        try:
            import yaml
            # Simple fallback format if no yaml module
            yaml_content = f"model: {model}\nreasoning_model: {reasoning_model}\noutput_format: {out_format}\nauto_tune: {str(auto_tune).lower()}\nskip_rag: {str(skip_rag).lower()}\nfast_mode: {str(fast_mode).lower()}\nrotate_models: {str(rotate_models).lower()}\nturbo: {str(turbo).lower()}\n"
            with open(config_path, 'w') as f:
                f.write(yaml_content)
            console.print(f"[green][+] Saved config to {config_path}[/green]")
        except Exception as e:
            console.print(f"[red][!] Failed to save configuration: {e}[/red]")

    return argparse.Namespace(
        workspace=workspace,
        model=None if auto_tune else model,
        detect_model=None,
        fix_model=None,
        reasoning_model=reasoning_model or None,
        discord_webhook=None,
        auto_tune=auto_tune,
        fix=apply_fixes,
        fix_code=fix_code,
        ci=False,
        verbose=verbose,
        format=out_format,
        output=None,
        fail_on_risk="HIGH",
        skip_rag=skip_rag,
        max_files=None,
        max_file_size=None,
        include=include_pattern,
        exclude=None,
        workers=None,
        ollama_urls=None,
        fast=fast_mode,
        batch_size=None,
        clear_cache=None,
        no_gitignore=False,
        turbo=turbo,
        keep_clone=False,
        rules=None,
        force_full_scan=None,
        rotate_models=rotate_models,
    )


def _resolve_workspace(workspace: str, keep_clone: bool = False) -> tuple[str, bool]:
    """Resolve a workspace argument that may be a git URL.

    Returns (local_path, is_temp_clone).
    If the workspace is a git URL it will be shallow-cloned into a temp dir.
    """
    if not _GIT_URL_PATTERN.match(workspace):
        # Plain local path
        return os.path.abspath(workspace), False

    # Extract repo name for folder naming
    repo_name = workspace.rstrip("/").split("/")[-1].removesuffix(".git")
    clone_dir = os.path.join(tempfile.gettempdir(), f"dockdesk_{repo_name}")

    if os.path.isdir(clone_dir):
        console.print(f"[yellow][*] Using existing clone: {clone_dir}[/yellow]")
    else:
        console.print(f"[yellow][*] Cloning {workspace} ...[/yellow]")
        result = subprocess.run(
            ["git", "clone", "--depth", "1", workspace, clone_dir],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            console.print(f"[bold red][-] Clone failed: {result.stderr.strip()}[/bold red]")
            sys.exit(1)
        console.print(f"[green][+] Cloned to {clone_dir}[/green]")

    if not keep_clone:
        _temp_clone_dirs.append(clone_dir)

    return clone_dir, True


def run_audit(args):
    """Run the main audit workflow."""
    from dockdesk.graph import create_audit_graph
    from dockdesk.config import build_config, OutputFormat, RiskLevel
    from dockdesk.models import (
        auto_select_model, validate_model, get_model_info,
        get_model_recommendation_message, count_lines_of_code,
        DEFAULT_MODEL, DEFAULT_REASONING_MODEL,
        get_available_ollama_models, is_model_audit_suitable,
    )
    from dockdesk.changelog import ChangelogWriter
    from dockdesk.fixer import apply_fixes_batch

    # Resolve git URLs → local clone BEFORE building config
    resolved_workspace, is_clone = _resolve_workspace(
        args.workspace, keep_clone=getattr(args, 'keep_clone', False)
    )

    # Build config from CLI args
    cli_args = {
        "workspace": resolved_workspace,
        "model": args.model,
        "detect_model": getattr(args, 'detect_model', None),
        "fix_model": getattr(args, 'fix_model', None),
        "reasoning_model": getattr(args, 'reasoning_model', None),
        "discord_webhook": getattr(args, 'discord_webhook', None),
        "auto_tune": args.auto_tune,
        "auto_fix": args.fix,
        "fix_code": args.fix_code,
        "ci_mode": args.ci,
        "verbose": args.verbose,
        "output_format": args.format,
        "output_file": args.output,
        "fail_on_risk": args.fail_on_risk,
        "skip_rag": args.skip_rag,
        # Scaling options
        "max_files": getattr(args, 'max_files', None),
        "max_file_size": getattr(args, 'max_file_size', None),
        "include_patterns": getattr(args, 'include', None),
        "exclude_patterns": getattr(args, 'exclude', None),
        "workers": getattr(args, 'workers', None),
        "ollama_urls": getattr(args, 'ollama_urls', None),
        "fast_mode": getattr(args, 'fast', None),
        "batch_size": getattr(args, 'batch_size', None),
        "clear_cache": getattr(args, 'clear_cache', None),
        "respect_gitignore": not getattr(args, 'no_gitignore', False) if hasattr(args, 'no_gitignore') else None,
        "turbo": getattr(args, 'turbo', None),
        "force_full_scan": getattr(args, 'force_full_scan', None),
        "rotate_models": getattr(args, 'rotate_models', None),
    }

    # Parse --rules into list
    rules_str = getattr(args, 'rules', None)
    if rules_str:
        cli_args["custom_rules"] = [r.strip() for r in rules_str.split(",") if r.strip()]

    profile_name = getattr(args, 'profile', None)
    config = build_config(cli_args, resolved_workspace, profile=profile_name)

    if profile_name:
        console.print(f"[dim]  Profile: {profile_name}[/dim]")

    # Apply turbo overrides (aggressive speed defaults)
    if config.turbo:
        config.fast_mode = True
        config.skip_rag = True
        if config.batch_size <= 5:
            config.batch_size = 8
        if config.workers <= 0:
            config.workers = 4
        console.print("[white][*] Turbo mode: --fast --skip-rag --batch-size 8 --workers 4[/white]")

    workspace = config.workspace

    # Model selection
    model = config.model
    model_tier = "unknown"
    # Defer LOC counting - will be done lazily or after discovery
    total_loc = 0

    # Resolve reasoning model
    reasoning_model = config.reasoning_model or DEFAULT_REASONING_MODEL
    if not config.reasoning_model and config.fix_model:
        reasoning_model = config.fix_model

    # In chat mode, startup animation is already shown on CLI entry.
    from_chat = bool(getattr(args, '_from_chat', False))
    skip_animation = bool(
        from_chat
        or config.fast_mode
        or config.ci_mode
        or getattr(args, 'turbo', False)
        or os.environ.get('CI')
    )
    from dockdesk import __version__ as _ver
    _print_loading(skip=skip_animation, version=_ver)

    if config.auto_tune:
        model, reason = auto_select_model(workspace)
        console.print(f"[white][>] Auto-tuned model: {model} ({reason})[/white]")
        model_info = get_model_info(model)
        model_tier = model_info.tier.value if model_info else "unknown"
        # LOC is counted inside auto_select_model - retrieve it once
        total_loc = count_lines_of_code(workspace)
    else:
        is_valid, message = validate_model(model, strict=False)
        if not is_valid:
            console.print(f"[bold white][-] {message}[/bold white]")
            if config.ci_mode:
                sys.exit(1)
            return
        console.print(f"[dim]{message}[/dim]")

        rec_message = get_model_recommendation_message(model, workspace)
        console.print(f"[dim]{rec_message}[/dim]")

        model_info = get_model_info(model)
        model_tier = model_info.tier.value if model_info else "unknown"

    # Build info lines for the startup panel
    _scan_mode = "turbo" if config.turbo else ("fast" if config.fast_mode else "standard")
    _rules_tag = f"  Rules: {len(config.custom_rules)} custom" if config.custom_rules else ""
    _rag_tag = "skip-rag" if config.skip_rag else "rag"

    from dockdesk.ui import print_config_panel
    print_config_panel(
        workspace=workspace,
        models=f"{model} ({model_tier}) · {reasoning_model}",
        loc=f"{total_loc:,}",
        exec_mode=f"{_scan_mode} | {_rag_tag}{_rules_tag}",
        out_format=config.output_format.name,
        risk_thres=config.fail_on_risk.name
    )

    from dockdesk.rag import HAS_RAG_DEPS
    if not config.skip_rag and not HAS_RAG_DEPS:
        console.print("[bold yellow][!] RAG Warning:[/bold yellow] RAG dependencies (chromadb, sentence_transformers) are not installed. Contextual search will be bypassed.")

    if getattr(config, "rotate_models", False):
        available = [m for m in get_available_ollama_models() if is_model_audit_suitable(m)]
        if available:
            preview = ", ".join(available[:6])
            more = f" (+{len(available) - 6} more)" if len(available) > 6 else ""
            console.print(f"[dim]  Rotation: enabled ({len(available)} models) -> {preview}{more}[/dim]")
        else:
            console.print("[dim]  Rotation: requested but no local audit-suitable models were found[/dim]")

    changelog = ChangelogWriter(workspace, config.changelog_file) if config.enable_changelog else None

    # Check Ollama health
    import requests
    ollama_url = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    if getattr(config, "ollama_urls", None):
        ollama_url = config.ollama_urls[0]
    try:
        requests.get(f"{ollama_url}/api/tags", timeout=3).raise_for_status()
    except Exception as e:
        console.print(f"\n[bold red][-] Ollama Health Check Failed:[/bold red] Could not connect to {ollama_url}")
        console.print(f"[red]Error:[/red] [dim]{e}[/dim]")
        console.print("[yellow]Is Ollama running? Try starting it with 'ollama serve'.[/yellow] \n")
        return 1

    app = create_audit_graph()

    initial_state = {
        "workspace_path": workspace,
        "discovered_files": [],
        "changed_files": [],
        "file_contents": {},
        "file_hashes": {},
        "doc_sources": [],
        "context_data": "",
        "code_findings": [],
        "audit_results": [],
        "mermaid_graph": "",
        "discord_posted": None,
        "config": config,
        "model": model,
        "reasoning_model": reasoning_model,
        "model_tier": model_tier,
        "total_loc": total_loc,
    }

    try:
        with console.status("[bold cyan]Models warming up & auditing codebase...[/bold cyan]", spinner="dots"):
            result = app.invoke(initial_state)
        audit_results = result.get("audit_results", [])

        fix_results = None
        if config.auto_fix and audit_results:
            console.print("\n[bold white][*] Applying fixes...[/bold white]")
            fix_results = apply_fixes_batch(
                audit_results=audit_results,
                workspace=workspace,
                allow_code_fixes=config.fix_code,
                dry_run=False,
                interactive=not config.ci_mode
            )

        if changelog:
            changelog.finalize_run(
                audit_results=audit_results,
                config=config,
                files_discovered=len(result.get("discovered_files", [])),
                model=model,
                model_tier=model_tier,
                total_loc=total_loc,
                fix_results=fix_results
            )

        report_path = result.get("report_path", os.path.join(workspace, "audit_report.md"))

        if config.output_format == OutputFormat.JSON:
            json_output = {
                "status": "complete",
                "model": model,
                "model_tier": model_tier,
                "total_loc": total_loc,
                "files_audited": len(audit_results),
                "results": audit_results,
                "fixes_applied": len([f for f in (fix_results or []) if f.status.value == "applied"])
            }
            if config.output_file:
                with open(config.output_file, 'w') as f:
                    json.dump(json_output, f, indent=2, default=str)
                console.print(f"[white][+] JSON report: {config.output_file}[/white]")
            else:
                print(json.dumps(json_output, indent=2, default=str))

        elif config.output_format == OutputFormat.SARIF:
            sarif_output = generate_sarif(audit_results, workspace)
            sarif_path = config.output_file or os.path.join(workspace, "audit_report.sarif")
            with open(sarif_path, 'w') as f:
                json.dump(sarif_output, f, indent=2)
            console.print(f"[white][+] SARIF report: {sarif_path}[/white]")
        else:
            console.print()

        # ── Final summary panel ──
        from dockdesk.ui import print_summary_card
        _high = sum(1 for r in audit_results if r.get("risk") == "HIGH")
        _med = sum(1 for r in audit_results if r.get("risk") == "MEDIUM")
        _low = sum(1 for r in audit_results if r.get("risk") == "LOW")
        _pass = sum(1 for r in audit_results if r.get("status") == "PASS")
        _fail = sum(1 for r in audit_results if r.get("status") == "FAIL")

        print_summary_card(
            total=len(audit_results),
            pass_count=_pass,
            fail_count=_fail,
            high=_high,
            med=_med,
            low=_low,
            report_path=report_path,
            version=_ver
        )

        if config.ci_mode:
            high_risk_count = sum(1 for r in audit_results if r.get("risk") == "HIGH")
            medium_risk_count = sum(1 for r in audit_results if r.get("risk") == "MEDIUM")

            should_fail = False
            if config.fail_on_risk == RiskLevel.HIGH and high_risk_count > 0:
                should_fail = True
            elif config.fail_on_risk == RiskLevel.MEDIUM and (high_risk_count > 0 or medium_risk_count > 0):
                should_fail = True
            elif config.fail_on_risk == RiskLevel.LOW and audit_results:
                fail_count = sum(1 for r in audit_results if r.get("status") == "FAIL")
                should_fail = fail_count > 0

            if should_fail:
                console.print(f"[bold red][-] CI gate failed: risk threshold exceeded ({config.fail_on_risk.value})[/bold red]")
                sys.exit(1)

    except Exception as e:
        console.print(f"[bold red][-] Audit Failed: {e}[/bold red]")
        if args.verbose:
            import traceback
            traceback.print_exc()
        if args.ci:
            sys.exit(1)


def generate_sarif(audit_results: list, workspace: str) -> dict:
    """Generate SARIF format output for IDE integration."""
    from dockdesk import __version__
    results = []

    for r in audit_results:
        if r.get("status") == "FAIL":
            level = "error" if r.get("risk") == "HIGH" else "warning"
            results.append({
                "ruleId": "dockdesk/semantic-drift",
                "level": level,
                "message": {
                    "text": r.get("summary", "Documentation drift detected")
                },
                "locations": [{
                    "physicalLocation": {
                        "artifactLocation": {
                            "uri": os.path.relpath(r.get("file", ""), workspace).replace("\\", "/")
                        }
                    }
                }],
                "fixes": [{
                    "description": {"text": "Apply suggested fix"},
                    "artifactChanges": [{
                        "artifactLocation": {
                            "uri": os.path.relpath(r.get("file", ""), workspace).replace("\\", "/")
                        },
                        "replacements": [{
                            "deletedRegion": {"startLine": 1},
                            "insertedContent": {"text": r.get("fix", "")}
                        }]
                    }]
                }] if r.get("fix") else []
            })

    return {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {
                "driver": {
                    "name": "DockDesk",
                    "version": __version__,
                    "informationUri": "https://github.com/dockdesk/auditor",
                    "rules": [{
                        "id": "dockdesk/semantic-drift",
                        "name": "SemanticDrift",
                        "shortDescription": {"text": "Documentation does not match code behavior"},
                        "fullDescription": {"text": "The documentation claims differ from actual code implementation"},
                        "helpUri": "https://github.com/dockdesk/auditor#semantic-drift"
                    }]
                }
            },
            "results": results
        }]
    }


def list_models_cmd(args):
    """List available audit-suitable models."""
    from dockdesk.models import print_model_list
    print_model_list()


def init_config_cmd(args):
    """Initialize a configuration file interactively."""
    _interactive_audit_options(args.workspace)
    console.print(f"[white][+] Finished configuration init.[/white]")
    console.print("[dim]Tip: Run 'dockdesk setup' to install Ollama and pull recommended models.[/dim]")


def setup_cmd(args):
    """Interactive Ollama setup: install Ollama and pull recommended models."""
    from dockdesk.setup import run_setup

    models = None
    if args.models:
        models = [m.strip() for m in args.models.split(",") if m.strip()]

    run_setup(skip_install=args.skip_install, models=models)


def discord_bot_cmd(args):
    """Launch Discord slash-command bot mode."""
    token = args.token or os.environ.get("DOCKDESK_DISCORD_BOT_TOKEN", "")
    if not token:
        console.print("[bold red][-] Missing Discord bot token. Use --token or DOCKDESK_DISCORD_BOT_TOKEN.[/bold red]")
        return

    workspace = os.path.abspath(args.workspace)
    guild_id = args.guild_id

    console.print("[white][*] Starting Discord bot mode...[/white]")
    console.print(f"[dim]  Workspace: {workspace}[/dim]")
    if guild_id:
        console.print(f"[dim]  Guild sync: {guild_id}[/dim]")
    else:
        console.print("[dim]  Guild sync: global (may take longer for command propagation)[/dim]")

    from dockdesk.discord import run_discord_bot
    run_discord_bot(workspace=workspace, token=token, guild_id=guild_id)


def open_react_dashboard_cmd(args):
    """Export data and open the React dashboard."""
    workspace = os.path.abspath(args.workspace)
    history = os.path.join(workspace, "audit_history.jsonl")
    
    install_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dashboard_dir = os.path.join(install_dir, "dashboard")
    public_dir = os.path.join(dashboard_dir, "public")
    data_file = os.path.join(public_dir, "dashboard_data.json")

    # Export audit data if history exists
    os.makedirs(public_dir, exist_ok=True)
    if os.path.exists(history):
        console.print("[white]Exporting audit data...[/white]")
        # Export logic internally
        dashboard_cmd(argparse.Namespace(workspace=workspace, export=data_file, open=False))
        console.print("[green]    Data exported[/green]")
    else:
        console.print("[yellow]  No audit history yet - generating empty dashboard data.[/yellow]")
        import json
        with open(data_file, "w", encoding="utf-8") as f:
            json.dump({
                "history": [],
                "latest": {
                    "metrics": {
                        "files_analyzed": 0,
                        "findings_count": 0,
                        "safe_to_push": 0,
                        "unsafe_to_push": 0
                    },
                    "pass_fail_distribution": {"PASS": 0, "FAIL": 0},
                    "risk_distribution": {"HIGH": 0, "MEDIUM": 0, "LOW": 0},
                    "models_per_file": {}
                },
                "accountability": {"developers": {}}
            }, f)

    # Check if node is available
    npx = shutil.which("npx")
    if not npx:
        console.print("\n[bold red]Node.js not found! Install from: https://nodejs.org[/bold red]")
        return

    # Install deps if needed
    node_modules = os.path.join(dashboard_dir, "node_modules")
    if not os.path.exists(node_modules):
        console.print("[white]Installing dashboard dependencies (first time only)...[/white]")
        subprocess.run(["npm", "install"], cwd=dashboard_dir, capture_output=True, shell=True)

    # Start Vite dev server
    console.print("[green] Starting dashboard at http://localhost:3000[/green]")
    console.print("[dim]   Press Ctrl+C to stop[/dim]\n")
    try:
        subprocess.run(["npx", "vite", "--port", "3000", "--open"], cwd=dashboard_dir, shell=True)
    except KeyboardInterrupt:
        console.print("\n\n[green] Dashboard stopped[/green]")


def _is_valid_dashboard_payload(path: str) -> bool:
    """Return True when an existing dashboard export has useful content."""
    try:
        if not os.path.exists(path):
            return False
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return False
        stats = data.get("stats", {})
        if stats.get("total_audits", 0) > 0:
            return True
        if data.get("recent_runs") or data.get("latest_run_files"):
            return True
        return False
    except Exception:
        return False


def dashboard_cmd(args):
    """Launch the dashboard or export data."""
    if getattr(args, 'open', False):
        return open_react_dashboard_cmd(args)
        
    from dockdesk.changelog import ChangelogReader

    changelog_path = os.path.join(args.workspace, "audit_history.jsonl")

    if not os.path.exists(changelog_path):
        console.print("[white][!] No audit history found. Run an audit first.[/white]")
        return

    reader = ChangelogReader(changelog_path)

    if args.export:
        export_path = os.path.abspath(args.export)
        
        # Prefer the rich dashboard data generated by the primary audit process
        enriched_data_path = os.path.join(args.workspace, "dashboard_data.json")
        if _is_valid_dashboard_payload(enriched_data_path):
            console.print(f"[white]Copying enriched dashboard data to {export_path}...[/white]")
            shutil.copy2(enriched_data_path, export_path)
            console.print(f"[green] Exported rich dashboard data: {export_path}[/green]")
            return

        # Fallback to basic export if the enriched version doesn't exist
        data = reader.export_for_dashboard()
        with open(export_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        console.print(f"[green] Exported basic dashboard data: {export_path}[/green]")
    else:
        section = getattr(args, 'section', 'summary')
        if section == "high_risk":
            runs = reader.get_runs(limit=10)
            if not runs:
                console.print("[white]No recent runs to check for high risk issues.[/white]")
                return
            
            console.print(f"\n[bold red]High Risk Summary (Last {len(runs)} Audits)[/bold red]")
            found = False
            for r in runs:
                high = r.get("risk_distribution", {}).get("HIGH", 0)
                if high > 0:
                    found = True
                    console.print(f"Run {r.get('timestamp')[:16].replace('T', ' ')}: [red]{high} HIGH RISK issues[/red]")
            if not found:
                console.print("[green]No HIGH RISK issues in recent audits. Great job![/green]")
            console.print("[dim]Use --export to view full details in the React dashboard.[/dim]\n")
            return
            
        elif section == "recent":
            runs = reader.get_runs(limit=5)
            if not runs:
                console.print("[white]No recent runs.[/white]")
                return
            
            table = Table(title="Recent Audit Runs", show_header=True)
            table.add_column("Date", style="dim")
            table.add_column("Files")
            table.add_column("Pass", style="green")
            table.add_column("Fail", style="red")
            
            for r in runs:
                date = r.get("timestamp", "")[:16].replace("T", " ")
                files = str(r.get("files_audited", 0))
                passed = str(r.get("pass_count", 0))
                fail = str(r.get("fail_count", 0))
                table.add_row(date, files, passed, fail)
            console.print()
            console.print(table)
            console.print()
            return

        # default to summary
        stats = reader.get_stats_summary()
        console.print(Panel.fit(
            f"[bold cyan]DockDesk Audit Statistics[/bold cyan]\n\n"
            f"  [bold white]Total Audits[/bold white]   {stats.get('total_audits', 0)}\n"
            f"  [bold white]Files Audited[/bold white]  {stats.get('total_files_audited', 0):,}\n"
            f"  [bold white]Fixes Applied[/bold white]  {stats.get('total_fixes_applied', 0)}\n"
            f"  [bold white]Avg Duration[/bold white]   {stats.get('average_duration_seconds', 0):.1f}s\n\n"
            f"  [dim]Risk Distribution:[/dim]\n"
            f"    [red]HIGH[/red]   {stats.get('risk_totals', {}).get('HIGH', 0)}\n"
            f"    [yellow]MEDIUM[/yellow] {stats.get('risk_totals', {}).get('MEDIUM', 0)}\n"
            f"    [green]LOW[/green]    {stats.get('risk_totals', {}).get('LOW', 0)}\n\n"
            f"  [dim]Use --export <file.json> to export for React dashboard[/dim]",
            border_style="cyan",
            padding=(0, 2),
        ))


def add_audit_args(parser):
    """Add audit-related arguments to a parser."""
    parser.add_argument("--workspace", "-w", default=".", help="Workspace path to audit")
    parser.add_argument("--model", "-m", default=None, help="Ollama model to use (default: qwen2.5-coder:7b)")
    parser.add_argument("--detect-model", default=None,
                       help="[DEPRECATED] Use --reasoning-model. Model for code detection")
    parser.add_argument("--fix-model", default=None,
                       help="[DEPRECATED] Alias for --reasoning-model")
    parser.add_argument("--reasoning-model", default=None,
                       help="DeepSeek-R1 reasoning model for risk assessment (default: deepseek-r1:1.5b)")
    parser.add_argument("--discord-webhook", default=None,
                       help="Discord webhook URL for audit notifications")
    parser.add_argument("--auto-tune", action="store_true", help="Auto-select model based on codebase size (LOC)")

    parser.add_argument("--fix", action="store_true", help="Automatically apply documentation fixes")
    parser.add_argument("--fix-code", action="store_true", help="Also apply code fixes (use with caution)")

    parser.add_argument("--format", "-f", choices=["md", "json", "sarif"], default="md",
                       help="Output format (default: md)")
    parser.add_argument("--output", "-o", metavar="FILE", help="Output file path")

    parser.add_argument("--ci", action="store_true", help="CI mode (non-interactive, exit codes)")
    parser.add_argument("--fail-on-risk", choices=["HIGH", "MEDIUM", "LOW"], default="HIGH",
                       help="Risk level that triggers CI failure (default: HIGH)")

    parser.add_argument("--skip-rag", action="store_true", help="Skip RAG retrieval for faster audits")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    scale_group = parser.add_argument_group("scaling", "Monorepo & performance options")
    scale_group.add_argument("--max-files", type=int, default=None,
                            help="Max files to analyze (0=unlimited)")
    scale_group.add_argument("--max-file-size", type=int, default=None, metavar="BYTES",
                            help="Skip files larger than N bytes (default: 512000 = 500KB)")
    scale_group.add_argument("--include", default=None, metavar="GLOBS",
                            help="Comma-separated include globs, e.g. 'src/**,lib/**'")
    scale_group.add_argument("--exclude", default=None, metavar="GLOBS",
                            help="Comma-separated exclude globs, e.g. 'generated/**,vendor/**'")
    scale_group.add_argument("--workers", type=int, default=None,
                            help="Parallel worker threads (default: auto)")
    scale_group.add_argument("--ollama-urls", default=None, metavar="URLS",
                            help="Comma-separated Ollama endpoints for distributed inference")
    scale_group.add_argument("--fast", action="store_true", default=None,
                            help="Fast mode: skip reasoning for LOW-risk files, batch analysis")
    scale_group.add_argument("--batch-size", type=int, default=None,
                            help="Files per batched LLM call (default: 5)")
    scale_group.add_argument("--clear-cache", action="store_true", default=None,
                            help="Clear result cache before running")
    scale_group.add_argument("--no-gitignore", action="store_true", default=False,
                            help="Ignore .gitignore rules during discovery")
    scale_group.add_argument("--turbo", action="store_true", default=None,
                            help="Turbo mode: --fast --batch-size 8 --workers 4 --skip-rag combined")
    scale_group.add_argument("--keep-clone", action="store_true", default=False,
                            help="Keep temporary git clone after audit (when using a URL as workspace)")
    scale_group.add_argument("--rules", default=None, metavar="RULES",
                            help="Comma-separated custom audit rules injected into LLM prompts")
    scale_group.add_argument("--force-full-scan", action="store_true", default=None,
                            help="Skip git/merkle diff, audit ALL discovered files")
    scale_group.add_argument("--rotate-models", action="store_true", default=None,
                            help="Round-robin code analysis across local audit-suitable models")


def main():
    """Main entry point for the dockdesk CLI."""
    from dockdesk import __version__
    import sys

    try:
        from dockdesk.models import get_available_ollama_models
        from dockdesk.setup import run_setup
        from rich.console import Console
        
        console = Console()
        
        # If no models are available and the user just typed 'dockdesk'
        if not get_available_ollama_models() and len(sys.argv) <= 1:
            console.print("\n[bold yellow]Welcome to DockDesk![/bold yellow] No local models detected.")
            console.print("[dim]Starting first-run setup to install Ollama and recommended models...[/dim]\n")
            run_setup(skip_install=False)
            console.print("\n[green]Setup complete. Starting interactive chat interface...[/green]\n")
    except Exception:
        pass

    # No args -> chat interface
    if len(sys.argv) == 1:
        _chat_interface()
        return

    parser = argparse.ArgumentParser(
        prog="dockdesk",
        description="DockDesk - Semantic Documentation & Code Auditor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  dockdesk audit /path/to/repo             # Audit a target repo
  dockdesk audit --auto-tune --fix         # Auto-select model + auto-fix
  dockdesk audit --profile strict          # Use the 'strict' profile
  dockdesk audit --ci --fail-on-risk HIGH  # CI mode
  dockdesk audit --format sarif            # SARIF output for VS Code
  dockdesk list-models                     # Show available models
  dockdesk profile list                    # List available profiles
  dockdesk tui                             # Interactive terminal dashboard
  dockdesk completion                      # Shell completion setup
  dockdesk dashboard --open                # Launch React dashboard
    dockdesk discord-bot --workspace .       # Run Discord slash-command bot
  dockdesk setup                           # Install Ollama + pull models
        """
    )
    parser.add_argument("--version", action="version", version=f"dockdesk {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # audit subcommand
    audit_parser = subparsers.add_parser("audit", help="Run semantic audit")
    add_audit_args(audit_parser)

    # list-models subcommand
    list_parser = subparsers.add_parser("list-models", help="List audit-suitable models")
    list_parser.set_defaults(func=list_models_cmd)

    # init subcommand
    init_parser = subparsers.add_parser("init", help="Initialize configuration file")
    init_parser.add_argument("--workspace", default=".", help="Workspace path")
    init_parser.add_argument("--force", action="store_true", help="Overwrite existing config")
    init_parser.set_defaults(func=init_config_cmd)

    # dashboard subcommand
    dash_parser = subparsers.add_parser("dashboard", help="View or export audit statistics")
    dash_parser.add_argument("--workspace", default=".", help="Workspace path")
    dash_parser.add_argument("--export", metavar="FILE", help="Export data to JSON file")
    dash_parser.add_argument("--open", action="store_true", help="Launch the React visual dashboard")
    dash_parser.set_defaults(func=dashboard_cmd)

    # setup subcommand
    setup_parser = subparsers.add_parser("setup", help="Install Ollama and pull recommended models")
    setup_parser.add_argument("--skip-install", action="store_true",
                              help="Skip Ollama installation check (only pull models)")
    setup_parser.add_argument("--models", default=None, metavar="MODELS",
                              help="Comma-separated list of models to pull (overrides defaults)")
    setup_parser.set_defaults(func=setup_cmd)

    # discord-bot subcommand
    dcb_parser = subparsers.add_parser("discord-bot", help="Run Discord bot with slash commands")
    dcb_parser.add_argument("--workspace", default=".", help="Workspace path")
    dcb_parser.add_argument("--token", default=None, help="Discord bot token (or DOCKDESK_DISCORD_BOT_TOKEN)")
    dcb_parser.add_argument("--guild-id", type=int, default=None, help="Optional guild ID for faster slash-command sync")
    dcb_parser.set_defaults(func=discord_bot_cmd)

    # profile subcommand
    profile_parser = subparsers.add_parser("profile", help="Manage audit profiles")
    profile_sub = profile_parser.add_subparsers(dest="profile_action")
    profile_sub.add_parser("list", help="List available profiles")
    profile_create = profile_sub.add_parser("create", help="Create a new profile")
    profile_create.add_argument("name", help="Profile name")
    profile_show = profile_sub.add_parser("show", help="Show profile details")
    profile_show.add_argument("name", help="Profile name")
    profile_init = profile_sub.add_parser("init", help="Initialize global config")

    # tui subcommand
    tui_parser = subparsers.add_parser("tui", help="Interactive terminal dashboard")
    tui_parser.add_argument("--workspace", default=".", help="Workspace path")

    # completion subcommand
    comp_parser = subparsers.add_parser("completion", help="Shell completion setup")
    comp_parser.add_argument("shell", nargs="?", default="auto",
                            choices=["bash", "zsh", "fish", "auto"],
                            help="Shell type (default: auto-detect)")

    # hooks subcommand
    hooks_parser = subparsers.add_parser("hooks", help="Manage git pre-push audit hooks")
    hooks_sub = hooks_parser.add_subparsers(dest="hooks_action")
    hooks_install = hooks_sub.add_parser("install", help="Install pre-push audit hook")
    hooks_install.add_argument("--workspace", default=".", help="Workspace path")
    hooks_uninstall = hooks_sub.add_parser("uninstall", help="Remove pre-push audit hook")
    hooks_uninstall.add_argument("--workspace", default=".", help="Workspace path")
    hooks_status_p = hooks_sub.add_parser("status", help="Check hook installation status")
    hooks_status_p.add_argument("--workspace", default=".", help="Workspace path")

    # pipeline subcommand
    pipeline_parser = subparsers.add_parser("pipeline", help="Monitor the CI/CD pipeline runs")
    pipeline_parser.add_argument("--workspace", default=".", help="Workspace path")
    pipeline_parser.set_defaults(func=pipeline_cmd)

    # Backward compat: audit args on root parser
    add_audit_args(parser)

    # Enable argcomplete if available
    try:
        import argcomplete
        argcomplete.autocomplete(parser)
    except ImportError:
        pass

    args = parser.parse_args()

    if args.command == "list-models":
        list_models_cmd(args)
    elif args.command == "init":
        init_config_cmd(args)
    elif args.command == "dashboard":
        dashboard_cmd(args)
    elif args.command == "setup":
        setup_cmd(args)
    elif args.command == "discord-bot":
        discord_bot_cmd(args)
    elif args.command == "profile":
        _handle_profile_cmd(args)
    elif args.command == "tui":
        from dockdesk.tui import launch_tui
        launch_tui(os.path.abspath(args.workspace))
    elif args.command == "completion":
        _handle_completion_cmd(args)
    elif args.command == "hooks":
        _handle_hooks_cmd(args)
    elif args.command == "pipeline":
        pipeline_cmd(args)
    else:
        run_audit(args)


def _handle_profile_cmd(args) -> None:
    """Handle `dockdesk profile` subcommands."""
    from dockdesk.profiles import (
        list_profiles, print_profile_list, print_profile_detail,
        create_profile, init_global_config
    )

    action = getattr(args, 'profile_action', None)
    if action == "list":
        print_profile_list()
    elif action == "create":
        path = create_profile(args.name)
        console.print(f"[green] Profile created: {path}[/green]")
    elif action == "show":
        print_profile_detail(args.name)
    elif action == "init":
        path = init_global_config()
        console.print(f"[green] Global config: {path}[/green]")
    else:
        print_profile_list()


def _handle_completion_cmd(args) -> None:
    """Print shell completion setup instructions."""
    shell = args.shell
    if shell == "auto":
        shell = os.environ.get("SHELL", "").split("/")[-1] or "bash"

    console.print(Panel(
        f"[bold #FF1493]Shell Completion Setup ({shell})[/bold #FF1493]\n",
        border_style="#8A2BE2",
    ))

    if shell == "bash":
        console.print(
            '  [#DA70D6]1.[/#DA70D6] [white]pip install argcomplete[/white]\n'
            '  [#DA70D6]2.[/#DA70D6] [white]Add to ~/.bashrc:[/white]\n'
            '     [#FF69B4]eval "$(register-python-argcomplete dockdesk)"[/#FF69B4]\n'
            '  [#DA70D6]3.[/#DA70D6] [white]Restart your shell[/white]'
        )
    elif shell == "zsh":
        console.print(
            '  [#DA70D6]1.[/#DA70D6] [white]pip install argcomplete[/white]\n'
            '  [#DA70D6]2.[/#DA70D6] [white]Add to ~/.zshrc:[/white]\n'
            '     [#FF69B4]autoload -U bashcompinit && bashcompinit[/#FF69B4]\n'
            '     [#FF69B4]eval "$(register-python-argcomplete dockdesk)"[/#FF69B4]\n'
            '  [#DA70D6]3.[/#DA70D6] [white]Restart your shell[/white]'
        )
    elif shell == "fish":
        console.print(
            '  [#DA70D6]1.[/#DA70D6] [white]pip install argcomplete[/white]\n'
            '  [#DA70D6]2.[/#DA70D6] [white]Run:[/white]\n'
            '     [#FF69B4]register-python-argcomplete --shell fish dockdesk > ~/.config/fish/completions/dockdesk.fish[/#FF69B4]\n'
            '  [#DA70D6]3.[/#DA70D6] [white]Restart your shell[/white]'
        )
    else:
        console.print(f"[yellow]Unsupported shell: {shell}[/yellow]")


def _handle_hooks_cmd(args) -> None:
    """Handle `dockdesk hooks` subcommands."""
    from dockdesk.hooks import install_hooks, uninstall_hooks, hooks_status

    action = getattr(args, 'hooks_action', None)
    workspace = os.path.abspath(getattr(args, 'workspace', '.'))

    if action == "install":
        install_hooks(workspace)
    elif action == "uninstall":
        uninstall_hooks(workspace)
    elif action == "status":
        hooks_status(workspace)
    else:
        hooks_status(workspace)


def pipeline_cmd(args):
    """Handle `dockdesk pipeline` command to display CI/CD pipeline statistics and runs."""
    from dockdesk.changelog import ChangelogReader
    from rich.table import Table
    from rich.panel import Panel
    from rich.console import Console
    
    console = Console()
    workspace = os.path.abspath(args.workspace)
    history_file = os.path.join(workspace, "audit_history.jsonl")
    
    reader = ChangelogReader(history_file)
    data = reader.export_for_dashboard()
    pipeline = data.get("pipeline_monitoring", {})
    
    if not pipeline or pipeline.get("total_runs", 0) == 0:
        console.print(Panel(
            "[bold yellow]No CI/CD pipeline runs detected yet![/bold yellow]\n\n"
            "To track pipeline runs, trigger an audit in CI mode by using the [bold]--ci[/bold] flag:\n"
            "[cyan]dockdesk audit --ci[/cyan]",
            border_style="yellow",
            title="CI/CD Pipeline Monitoring"
        ))
        return
        
    total = pipeline.get("total_runs", 0)
    rate = pipeline.get("success_rate", 100)
    avg_dur = pipeline.get("average_duration", 0.0)
    
    # Styled Panel with Pipeline Health
    rate_color = "green" if rate >= 80 else "yellow" if rate >= 50 else "red"
    console.print(Panel(
        f"  [bold]Total CI/CD Runs:[/bold] {total}\n"
        f"  [bold]Overall Success Rate:[/bold] [{rate_color}]{rate}%[/{rate_color}]\n"
        f"  [bold]Average Duration:[/bold] {avg_dur}s",
        border_style="#8A2BE2",
        title="[bold #FF1493]CI/CD Pipeline Health[/bold #FF1493]",
        title_align="left"
    ))
    
    # Table of Pipeline Runs
    table = Table(title="[bold #FF69B4]Recent CI/CD Pipeline Runs[/bold #FF69B4]", border_style="#8A2BE2", title_style="bold")
    table.add_column("Timestamp", style="dim", width=20)
    table.add_column("Run ID", style="cyan", width=22)
    table.add_column("Branch", style="magenta", width=12)
    table.add_column("Commit", style="dim", width=10)
    table.add_column("Status", width=10)
    table.add_column("Pass / Fail", width=12)
    table.add_column("Duration", style="yellow", width=10)
    
    for r in pipeline.get("runs", []):
        status_str = "[bold green]PASSED[/bold green]" if r["status"] == "PASS" else "[bold red]FAILED[/bold red]"
        pass_fail = f"[green]{r['pass_count']}[/green] / [red]{r['fail_count']}[/red]"
        table.add_row(
            r["timestamp"][:19].replace("T", " "),
            r["run_id"],
            r["branch"] or "N/A",
            r["commit"] or "N/A",
            status_str,
            pass_fail,
            f"{r['duration']:.2f}s"
        )
        
    console.print(table)


if __name__ == "__main__":
    main()
