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
if sys.platform == 'win32' and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
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
        "provider": getattr(args, 'provider', 'ollama'),
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

    provider_name = getattr(config, "provider", "ollama").lower()

    if provider_name == "ollama":
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
    else:
        # Non-ollama provider
        model_tier = "cloud"
        total_loc = count_lines_of_code(workspace)

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
    
    if provider_name in ["openai", "anthropic"]:
        console.print(f"[bold yellow][!] Privacy Warning:[/bold yellow] Sending code to {provider_name.upper()} — see docs on data handling.")
    elif provider_name == "ollama":
        # Check Ollama health only if using Ollama
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
    """Initialize a configuration file with defaults."""
    config_path = os.path.join(args.workspace, "dockdesk.yml")
    yaml_content = "model: qwen2.5-coder:3b\nreasoning_model: deepseek-r1:1.5b\noutput_format: md\nauto_tune: false\nskip_rag: false\nfast_mode: false\nrotate_models: false\nturbo: false\n"
    try:
        with open(config_path, 'w') as f:
            f.write(yaml_content)
        console.print(f"[green][+] Saved config to {config_path}[/green]")
    except Exception as e:
        console.print(f"[red][!] Failed to save configuration: {e}[/red]")
    console.print(f"[white][+] Finished configuration init.[/white]")
    console.print("[dim]Tip: Run 'dockdesk setup' to install Ollama and pull recommended models.[/dim]")


def report_cmd(args):
    """Print the last audit report from history."""
    workspace = os.path.abspath(args.workspace)
    history_file = os.path.join(workspace, "audit_history.jsonl")
    if not os.path.exists(history_file):
        console.print("[white][!] No audit history found. Run an audit first.[/white]")
        return
    try:
        with open(history_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        if not lines:
            console.print("[white][!] Audit history is empty.[/white]")
            return
        last_run = json.loads(lines[-1])
        console.print(Panel(
            f"[bold cyan]Last Audit Summary ({last_run.get('timestamp', '')[:16].replace('T', ' ')})[/bold cyan]\n\n"
            f"  [bold white]Files Audited[/bold white]  {last_run.get('files_audited', 0):,}\n"
            f"  [bold white]Pass / Fail[/bold white]    [green]{last_run.get('pass_count', 0)}[/green] / [red]{last_run.get('fail_count', 0)}[/red]\n"
            f"  [bold white]Avg Duration[/bold white]   {last_run.get('duration', 0):.1f}s\n\n"
            f"  [dim]Risk Distribution:[/dim]\n"
            f"    [red]HIGH[/red]   {last_run.get('risk_distribution', {}).get('HIGH', 0)}\n"
            f"    [yellow]MEDIUM[/yellow] {last_run.get('risk_distribution', {}).get('MEDIUM', 0)}\n"
            f"    [green]LOW[/green]    {last_run.get('risk_distribution', {}).get('LOW', 0)}\n",
            border_style="cyan"
        ))
    except Exception as e:
        console.print(f"[red]Error reading report: {e}[/red]")


def setup_cmd(args):
    """Interactive Ollama setup: install Ollama and pull recommended models."""
    from dockdesk.setup import run_setup

    models = None
    if args.models:
        models = [m.strip() for m in args.models.split(",") if m.strip()]

    run_setup(skip_install=args.skip_install, models=models)


def knowledge_graph_cmd(args):
    """Export the repository knowledge graph for standalone use."""
    from dockdesk.knowledge_graph import write_knowledge_graph_outputs

    workspace = os.path.abspath(args.workspace)
    output_path = os.path.abspath(args.output or os.path.join(workspace, "knowledge_graph.json"))
    markdown_path = os.path.abspath(args.markdown) if args.markdown else None
    dashboard_path = os.path.abspath(args.dashboard_data) if args.dashboard_data else None

    written = write_knowledge_graph_outputs(
        workspace=workspace,
        output_path=output_path,
        markdown_path=markdown_path,
        dashboard_data_path=dashboard_path,
    )

    console.print(f"[green][+] Knowledge graph exported: {written['graph_path']}[/green]")
    if written.get("markdown_path"):
        console.print(f"[dim]  Markdown summary: {written['markdown_path']}[/dim]")
    if written.get("dashboard_data_path"):
        console.print(f"[dim]  Dashboard payload: {written['dashboard_data_path']}[/dim]")


def add_audit_args(parser):
    """Add audit-related arguments to a parser."""
    parser.add_argument("--workspace", "-w", default=".", help="Workspace path to audit")
    parser.add_argument("--provider", choices=["ollama", "openai", "anthropic"], default="ollama", help="LLM provider (default: ollama)")
    parser.add_argument("--model", "-m", default=None, help="Model to use (default depends on provider)")
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
    import argparse

    try:
        from dockdesk.models import get_available_ollama_models
        from dockdesk.setup import run_setup
        
        # If no models are available and the user just typed 'dockdesk'
        if not get_available_ollama_models() and len(sys.argv) <= 1:
            console.print("\n[bold yellow]Welcome to DockDesk![/bold yellow] No local models detected.")
            console.print("[dim]Starting first-run setup to install Ollama and recommended models...[/dim]\n")
            run_setup(skip_install=False)
    except Exception:
        pass

    parser = argparse.ArgumentParser(
        prog="dockdesk",
        description="DockDesk - Semantic Documentation & Code Auditor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  dockdesk audit /path/to/repo             # Audit a target repo
  dockdesk audit --auto-tune --fix         # Auto-select model + auto-fix
  dockdesk report                          # View the last audit result
        """
    )
    parser.add_argument("--version", action="version", version=f"dockdesk {__version__}")
    parser.add_argument("--legacy", action="store_true", help=argparse.SUPPRESS)

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # audit subcommand
    audit_parser = subparsers.add_parser("audit", help="Run semantic audit")
    add_audit_args(audit_parser)

    # init subcommand
    init_parser = subparsers.add_parser("init", help="Initialize configuration file")
    init_parser.add_argument("--workspace", default=".", help="Workspace path")
    init_parser.add_argument("--force", action="store_true", help="Overwrite existing config")
    init_parser.set_defaults(func=init_config_cmd)

    # report subcommand
    report_parser = subparsers.add_parser("report", help="View the last audit result")
    report_parser.add_argument("--workspace", default=".", help="Workspace path")
    report_parser.set_defaults(func=report_cmd)

    # Legacy commands
    if "--legacy" in sys.argv:
        list_parser = subparsers.add_parser("list-models", help="List audit-suitable models")
        list_parser.set_defaults(func=list_models_cmd)
        
        kg_parser = subparsers.add_parser("knowledge-graph", help="Export the repository knowledge graph")
        kg_parser.add_argument("--workspace", default=".", help="Workspace path")
        kg_parser.add_argument("--output", metavar="FILE", help="Graph JSON output path")
        kg_parser.add_argument("--markdown", metavar="FILE", help="Optional Markdown summary output path")
        kg_parser.add_argument("--dashboard-data", metavar="FILE", help="Optional dashboard payload output path")
        kg_parser.set_defaults(func=knowledge_graph_cmd)

        setup_parser = subparsers.add_parser("setup", help="Install Ollama and pull recommended models")
        setup_parser.add_argument("--skip-install", action="store_true",
                                  help="Skip Ollama installation check (only pull models)")
        setup_parser.add_argument("--models", default=None, metavar="MODELS",
                                  help="Comma-separated list of models to pull (overrides defaults)")
        setup_parser.set_defaults(func=setup_cmd)

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

    # If no args, print help
    if len(sys.argv) == 1:
        parser.print_help()
        return

    args, _ = parser.parse_known_args()

    if args.command == "list-models":
        list_models_cmd(args)
    elif args.command == "init":
        init_config_cmd(args)
    elif args.command == "report":
        report_cmd(args)
    elif args.command == "setup":
        setup_cmd(args)
    elif args.command == "knowledge-graph":
        knowledge_graph_cmd(args)
    elif args.command == "pipeline":
        pipeline_cmd(args)
    elif args.command == "audit":
        run_audit(args)
    else:
        # Default fallback if somehow command is none or unrecognized, run audit with default args
        run_audit(args)

if __name__ == "__main__":
    main()
