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


def _browse_for_workspace(start_dir: Path) -> Path | None:
    """Simple folder picker that works in plain terminals."""
    current = start_dir.resolve()

    while True:
        console.print(Panel(
            f"[bold #DA70D6]Folder Browser[/bold #DA70D6]\n"
            f"[white]Current:[/white] [#FF69B4]{current}[/#FF69B4]\n"
            "[dim]Type a number to enter folder, '..' for parent, '.' to select this folder, 'q' to cancel.[/dim]",
            border_style="#8A2BE2"
        ))

        dirs: list[Path] = []
        try:
            dirs = sorted(
                [p for p in current.iterdir() if p.is_dir() and not p.name.startswith(".")],
                key=lambda p: p.name.lower()
            )
        except (PermissionError, OSError):
            console.print("[bold red][-] Cannot read this folder.[/bold red]")

        if not dirs:
            console.print("[yellow][*] No visible subfolders here.[/yellow]")
        else:
            max_show = min(len(dirs), 25)
            for idx in range(max_show):
                console.print(f"[#DA70D6]{idx + 1:>2}[/#DA70D6]  [#FF69B4]{dirs[idx].name}[/#FF69B4]")
            if len(dirs) > max_show:
                console.print(f"[dim]... and {len(dirs) - max_show} more[/dim]")

        choice = Prompt.ask("[#FF00FF]browse[/#FF00FF]").strip()

        if choice.lower() == "q":
            return None
        if choice == ".":
            return current
        if choice == "..":
            parent = current.parent
            current = parent if parent != current else current
            continue
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(dirs):
                current = dirs[idx]
                continue
        console.print("[yellow][!] Invalid choice.[/yellow]")


def _interactive_workspace_picker(default_base: Path) -> str | None:
    """Choose a workspace from discovered projects or manual browse."""
    base_dir = default_base.resolve()

    while True:
        console.print(Panel(
            f"[bold #FF1493]DockDesk Interactive Mode[/bold #FF1493]\n"
            f"[white]Scan root:[/white] [#FF69B4]{base_dir}[/#FF69B4]\n"
            "[dim]Choose a detected project, rescan a different root, or open folder browser.[/dim]",
            border_style="#8A2BE2"
        ))

        projects = _discover_projects(base_dir)
        if projects:
            _render_project_table(projects, base_dir)
            console.print("[dim]Commands: number = select, b = browse, r = rescan root, q = quit[/dim]")
        else:
            console.print("[yellow][!] No project folders detected in this root.[/yellow]")
            console.print("[dim]Commands: b = browse, r = rescan root, q = quit[/dim]")

        choice = Prompt.ask("[#FF00FF]select[/#FF00FF]").strip().lower()

        if choice == "q":
            return None
        if choice == "b":
            selected = _browse_for_workspace(base_dir)
            if selected:
                return str(selected)
            continue
        if choice == "r":
            new_root = Prompt.ask("[#DA70D6]New scan root[/#DA70D6]", default=str(base_dir)).strip()
            if new_root:
                candidate = Path(new_root).expanduser().resolve()
                if candidate.exists() and candidate.is_dir():
                    base_dir = candidate
                else:
                    console.print("[bold red][-] Invalid folder path.[/bold red]")
            continue
        if choice.isdigit() and projects:
            idx = int(choice) - 1
            if 0 <= idx < len(projects):
                return str(projects[idx][0].resolve())
        console.print("[yellow][!] Invalid choice.[/yellow]")


def _interactive_main_menu() -> None:
    """Main interactive flow for users running dockdesk with no args."""
    from dockdesk import __version__ as _ver

    _print_loading(skip=True, version=_ver)
    workspace = _interactive_workspace_picker(Path.cwd())
    if not workspace:
        console.print("[dim]Session closed.[/dim]")
        return

    while True:
        menu = Table(show_header=False, box=None)
        menu.add_column(style="bold #DA70D6", width=5)
        menu.add_column(style="#FF69B4")
        menu.add_row("1", "Run Audit")
        menu.add_row("2", "List Models")
        menu.add_row("3", "Open Dashboard Stats")
        menu.add_row("4", "Init Config")
        menu.add_row("5", "Change Workspace")
        menu.add_row("6", "Exit")

        console.print(Panel(
            menu,
            title=Text("[ Mission Menu ]", style="bold #FF1493"),
            subtitle=Text(f"Workspace: {workspace}", style="#DA70D6"),
            border_style="#8A2BE2"
        ))

        choice = Prompt.ask("[#FF00FF]action[/#FF00FF]", default="1").strip()

        if choice == "1":
            opts = _interactive_audit_options(workspace)
            if opts is not None:
                run_audit(opts)
        elif choice == "2":
            list_models_cmd(argparse.Namespace())
        elif choice == "3":
            dashboard_cmd(argparse.Namespace(workspace=workspace, export=None))
        elif choice == "4":
            init_config_cmd(argparse.Namespace(workspace=workspace, force=False))
        elif choice == "5":
            picked = _interactive_workspace_picker(Path(workspace))
            if picked:
                workspace = picked
        elif choice == "6":
            console.print("[dim]Session closed.[/dim]")
            return
        else:
            console.print("[yellow][!] Invalid choice.[/yellow]")


def _prompt_bool(label: str, default: bool = False) -> bool:
    """Prompt for yes/no using y/n with sensible defaults."""
    d = "y" if default else "n"
    value = Prompt.ask(label, default=d).strip().lower()
    return value in {"y", "yes", "true", "1"}


def _interactive_audit_options(workspace: str) -> argparse.Namespace | None:
    """Collect quick audit options from interactive mode."""
    console.print(Panel(
        "[bold #FF1493]Quick Audit Options[/bold #FF1493]\n"
        "[dim]Press Enter to accept defaults. Type 'q' to cancel and return.[/dim]",
        border_style="#8A2BE2"
    ))

    model = Prompt.ask("[#DA70D6]Code model[/#DA70D6]", default="qwen2.5-coder:7b").strip()
    if model.lower() == "q":
        return None

    auto_tune = _prompt_bool("[#DA70D6]Auto-tune model by LOC?[/#DA70D6]", default=False)
    reasoning_model = Prompt.ask("[#DA70D6]Reasoning model[/#DA70D6]", default="deepseek-r1:1.5b").strip()
    out_format = Prompt.ask("[#DA70D6]Output format (md/json/sarif)[/#DA70D6]", default="md").strip().lower()
    if out_format not in {"md", "json", "sarif"}:
        console.print("[yellow][!] Invalid format, using md.[/yellow]")
        out_format = "md"

    skip_rag = _prompt_bool("[#DA70D6]Skip RAG for speed?[/#DA70D6]", default=False)
    fast_mode = _prompt_bool("[#DA70D6]Enable fast mode?[/#DA70D6]", default=False)
    turbo = _prompt_bool("[#DA70D6]Enable turbo mode?[/#DA70D6]", default=False)
    apply_fixes = _prompt_bool("[#DA70D6]Apply documentation fixes?[/#DA70D6]", default=False)
    fix_code = _prompt_bool("[#DA70D6]Also allow code fixes?[/#DA70D6]", default=False) if apply_fixes else False
    verbose = _prompt_bool("[#DA70D6]Verbose output?[/#DA70D6]", default=False)

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
        include=None,
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
        DEFAULT_MODEL, DEFAULT_REASONING_MODEL
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
    }

    # Parse --rules into list
    rules_str = getattr(args, 'rules', None)
    if rules_str:
        cli_args["custom_rules"] = [r.strip() for r in rules_str.split(",") if r.strip()]

    config = build_config(cli_args, resolved_workspace)

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
    # Defer LOC counting — will be done lazily or after discovery
    total_loc = 0

    # Resolve reasoning model
    reasoning_model = config.reasoning_model or DEFAULT_REASONING_MODEL
    if not config.reasoning_model and config.fix_model:
        reasoning_model = config.fix_model

    # Skip animation in fast/CI mode for ~600ms savings
    skip_animation = bool(config.fast_mode or config.ci_mode or getattr(args, 'turbo', False) or os.environ.get('CI'))
    from dockdesk import __version__ as _ver
    _print_loading(skip=skip_animation, version=_ver)

    if config.auto_tune:
        model, reason = auto_select_model(workspace)
        console.print(f"[white][>] Auto-tuned model: {model} ({reason})[/white]")
        model_info = get_model_info(model)
        model_tier = model_info.tier.value if model_info else "unknown"
        # LOC is counted inside auto_select_model — retrieve it once
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

    changelog = ChangelogWriter(workspace, config.changelog_file) if config.enable_changelog else None
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
                    "version": "2.1.0",
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
    """Initialize a sample configuration file."""
    from dockdesk.config import create_sample_config

    config_content = create_sample_config(args.workspace, format="yaml")
    config_path = os.path.join(args.workspace, "dockdesk.yml")

    if os.path.exists(config_path) and not args.force:
        console.print(f"[white][!] Config already exists: {config_path}[/white]")
        console.print("Use --force to overwrite")
        return

    with open(config_path, 'w') as f:
        f.write(config_content)

    console.print(f"[white][+] Created config: {config_path}[/white]")
    console.print("[dim]Tip: Run 'dockdesk setup' to install Ollama and pull recommended models.[/dim]")


def setup_cmd(args):
    """Interactive Ollama setup: install Ollama and pull recommended models."""
    from dockdesk.setup import run_setup

    models = None
    if args.models:
        models = [m.strip() for m in args.models.split(",") if m.strip()]

    run_setup(skip_install=args.skip_install, models=models)


def dashboard_cmd(args):
    """Launch the dashboard or export data."""
    from dockdesk.changelog import ChangelogReader

    changelog_path = os.path.join(args.workspace, "audit_history.jsonl")

    if not os.path.exists(changelog_path):
        console.print("[white][!] No audit history found. Run an audit first.[/white]")
        return

    reader = ChangelogReader(changelog_path)

    if args.export:
        data = reader.export_for_dashboard()
        export_path = args.export
        with open(export_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        console.print(f"[green]✓ Exported dashboard data: {export_path}[/green]")
    else:
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


def main():
    """Main entry point for the dockdesk CLI."""
    from dockdesk import __version__

    # No args -> interactive mode with project picker and themed menus.
    if len(sys.argv) == 1:
        _interactive_main_menu()
        return

    parser = argparse.ArgumentParser(
        prog="dockdesk",
        description="DockDesk - Semantic Documentation & Code Auditor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  dockdesk audit /path/to/repo             # Audit a target repo
  dockdesk audit --auto-tune --fix         # Auto-select model + auto-fix
  dockdesk audit --model codellama:7b      # Use specific model
  dockdesk audit --ci --fail-on-risk HIGH  # CI mode
  dockdesk audit --format sarif            # SARIF output for VS Code
  dockdesk list-models                     # Show available models
  dockdesk init --workspace /path          # Create config file
  dockdesk dashboard --workspace /path     # View audit stats
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
    dash_parser.set_defaults(func=dashboard_cmd)

    # setup subcommand
    setup_parser = subparsers.add_parser("setup", help="Install Ollama and pull recommended models")
    setup_parser.add_argument("--skip-install", action="store_true",
                              help="Skip Ollama installation check (only pull models)")
    setup_parser.add_argument("--models", default=None, metavar="MODELS",
                              help="Comma-separated list of models to pull (overrides defaults)")
    setup_parser.set_defaults(func=setup_cmd)

    # Backward compat: audit args on root parser
    add_audit_args(parser)

    args = parser.parse_args()

    if args.command == "list-models":
        list_models_cmd(args)
    elif args.command == "init":
        init_config_cmd(args)
    elif args.command == "dashboard":
        dashboard_cmd(args)
    elif args.command == "setup":
        setup_cmd(args)
    else:
        run_audit(args)


if __name__ == "__main__":
    main()
