#!/usr/bin/env python3
"""
DockDesk - Semantic Documentation & Code Auditor

A local-first, AI-powered auditor that ensures code and documentation stay in sync.
Supports multiple Ollama models with auto-tuning based on codebase size.
"""

import argparse
import sys
import os
import json
import time
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console(highlight=False)

ASCII_BANNER = r"""
 ____   ___   ____ _  ______  _____ ____  _  __
|  _ \ / _ \ / ___| |/ /  _ \| ____/ ___|| |/ /
| | | | | | | |   | ' /| | | |  _| \___ \| ' / 
| |_| | |_| | |___| . \| |_| | |___ ___) | . \ 
|____/ \___/ \____|_|\_\____/|_____|____/|_|\_\
"""


def _print_loading():
    """Print retro ASCII loading animation."""
    console.print("[bold white]" + ASCII_BANNER + "[/bold white]")
    frames = [
        "[dim]> Initializing neural auditor...      [/dim]",
        "[dim]> Loading code analysis engine...      [/dim]",
        "[dim]> Connecting to local LLM backend...   [/dim]",
        "[dim]> System ready.                        [/dim]",
    ]
    for frame in frames:
        console.print(frame)
        time.sleep(0.15)
    console.print()


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
    
    # Build config from CLI args
    cli_args = {
        "workspace": args.workspace,
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
    }
    
    config = build_config(cli_args, args.workspace)
    workspace = config.workspace
    
    # Model selection
    model = config.model
    model_tier = "unknown"
    total_loc = count_lines_of_code(workspace)
    
    # Resolve reasoning model
    reasoning_model = config.reasoning_model or DEFAULT_REASONING_MODEL
    # Legacy: if fix_model was set, use it as reasoning_model fallback
    if not config.reasoning_model and config.fix_model:
        reasoning_model = config.fix_model
    
    _print_loading()

    if config.auto_tune:
        model, reason = auto_select_model(workspace)
        console.print(f"[white][>] Auto-tuned model: {model} ({reason})[/white]")
        model_info = get_model_info(model)
        model_tier = model_info.tier.value if model_info else "unknown"
    else:
        # Validate selected model
        is_valid, message = validate_model(model, strict=False)
        if not is_valid:
            console.print(f"[bold white][-] {message}[/bold white]")
            if config.ci_mode:
                sys.exit(1)
            return
        console.print(f"[dim]{message}[/dim]")
        
        # Show recommendation
        rec_message = get_model_recommendation_message(model, workspace)
        console.print(f"[dim]{rec_message}[/dim]")
        
        model_info = get_model_info(model)
        model_tier = model_info.tier.value if model_info else "unknown"
    
    console.print(Panel.fit(
        f"[bold white]DockDesk Dual-Model Auditor[/bold white]\n"
        f"Workspace: {workspace}\n"
        f"Code Agent: {model} ({model_tier})\n"
        f"Reasoning Agent: {reasoning_model}\n"
        f"LOC: {total_loc:,}",
        border_style="white"
    ))
    
    # Initialize changelog
    changelog = ChangelogWriter(workspace, config.changelog_file) if config.enable_changelog else None
    
    # Create and run the audit graph
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
        # Config & models
        "config": config,
        "model": model,
        "reasoning_model": reasoning_model,
        "model_tier": model_tier,
        "total_loc": total_loc,
    }
    
    try:
        result = app.invoke(initial_state)
        audit_results = result.get("audit_results", [])
        
        # Apply fixes if requested
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
        
        # Write changelog
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
        
        # Output handling
        report_path = result.get("report_path", "audit_report.md")
        
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
            sarif_path = config.output_file or "audit_report.sarif"
            with open(sarif_path, 'w') as f:
                json.dump(sarif_output, f, indent=2)
            console.print(f"[white][+] SARIF report: {sarif_path}[/white]")
        else:
            console.print(f"\n[bold white][+] Audit Complete. Report: {report_path}[/bold white]")
        
        # Risk gating for CI
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
                console.print(f"[bold white][-] ::error::Audit failed risk threshold ({config.fail_on_risk.value})[/bold white]")
                sys.exit(1)
                
    except Exception as e:
        console.print(f"[bold white][-] Audit Failed: {e}[/bold white]")
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
                    "version": "2.0.0",
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
        # Print stats summary
        stats = reader.get_stats_summary()
        console.print(Panel.fit(
            f"[bold white]DockDesk Audit Statistics[/bold white]\n\n"
            f"Total Audits: {stats.get('total_audits', 0)}\n"
            f"Files Audited: {stats.get('total_files_audited', 0):,}\n"
            f"Fixes Applied: {stats.get('total_fixes_applied', 0)}\n"
            f"Avg Duration: {stats.get('average_duration_seconds', 0):.1f}s\n\n"
            f"[dim]Risk Distribution:[/dim]\n"
            f"  HIGH: {stats.get('risk_totals', {}).get('HIGH', 0)}\n"
            f"  MEDIUM: {stats.get('risk_totals', {}).get('MEDIUM', 0)}\n"
            f"  LOW: {stats.get('risk_totals', {}).get('LOW', 0)}\n\n"
            f"[dim]Use --export <file.json> to export for React dashboard[/dim]",
            border_style="white"
        ))


def main():
    parser = argparse.ArgumentParser(
        description="DockDesk - Semantic Documentation & Code Auditor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python auditor_slm.py                    # Audit current directory
  python auditor_slm.py --auto-tune        # Auto-select best model for codebase
  python auditor_slm.py --model codellama:7b --fix  # Use specific model with auto-fix
  python auditor_slm.py --ci --fail-on-risk HIGH    # CI mode with risk gating
  python auditor_slm.py --format sarif     # Output SARIF for VS Code
  python auditor_slm.py list-models        # Show available models
  python auditor_slm.py dashboard --export data.json  # Export for React dashboard
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Main audit command (default)
    audit_parser = subparsers.add_parser("audit", help="Run semantic audit")
    add_audit_args(audit_parser)
    
    # List models command
    list_parser = subparsers.add_parser("list-models", help="List audit-suitable models")
    list_parser.set_defaults(func=list_models_cmd)
    
    # Init config command
    init_parser = subparsers.add_parser("init", help="Initialize configuration file")
    init_parser.add_argument("--workspace", default=".", help="Workspace path")
    init_parser.add_argument("--force", action="store_true", help="Overwrite existing config")
    init_parser.set_defaults(func=init_config_cmd)
    
    # Dashboard command
    dash_parser = subparsers.add_parser("dashboard", help="View or export audit statistics")
    dash_parser.add_argument("--workspace", default=".", help="Workspace path")
    dash_parser.add_argument("--export", metavar="FILE", help="Export data to JSON file")
    dash_parser.set_defaults(func=dashboard_cmd)
    
    # Add audit args to main parser for backward compatibility
    add_audit_args(parser)
    
    args = parser.parse_args()
    
    # Handle subcommands
    if args.command == "list-models":
        list_models_cmd(args)
    elif args.command == "init":
        init_config_cmd(args)
    elif args.command == "dashboard":
        dashboard_cmd(args)
    else:
        # Default: run audit
        run_audit(args)


def add_audit_args(parser):
    """Add audit-related arguments to a parser."""
    # Core options
    parser.add_argument("--workspace", "-w", default=".", help="Workspace path to audit")
    parser.add_argument("--model", "-m", default=None, help="Ollama model to use (default: qwen2.5-coder:7b)")
    parser.add_argument("--detect-model", default=None,
                       help="[DEPRECATED] Use --reasoning-model. Model for code detection (default: same as --model)")
    parser.add_argument("--fix-model", default=None,
                       help="[DEPRECATED] Alias for --reasoning-model")
    parser.add_argument("--reasoning-model", default=None,
                       help="DeepSeek-R1 reasoning model for risk assessment (default: deepseek-r1:1.5b)")
    parser.add_argument("--discord-webhook", default=None,
                       help="Discord webhook URL for audit notifications")
    parser.add_argument("--auto-tune", action="store_true", help="Auto-select model based on codebase size (LOC)")
    
    # Fix options
    parser.add_argument("--fix", action="store_true", help="Automatically apply documentation fixes")
    parser.add_argument("--fix-code", action="store_true", help="Also apply code fixes (use with caution)")
    
    # Output options
    parser.add_argument("--format", "-f", choices=["md", "json", "sarif"], default="md",
                       help="Output format (default: md)")
    parser.add_argument("--output", "-o", metavar="FILE", help="Output file path")
    
    # CI/CD options
    parser.add_argument("--ci", action="store_true", help="CI mode (non-interactive, exit codes)")
    parser.add_argument("--fail-on-risk", choices=["HIGH", "MEDIUM", "LOW"], default="HIGH",
                       help="Risk level that triggers CI failure (default: HIGH)")
    
    # Advanced options
    parser.add_argument("--skip-rag", action="store_true", help="Skip RAG retrieval for faster audits")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    # ── Monorepo Scaling ──────────────────────────────────────────────
    scale_group = parser.add_argument_group("scaling", "Monorepo & performance options")
    scale_group.add_argument("--max-files", type=int, default=None,
                            help="Max files to analyze (0=unlimited, default: config or unlimited)")
    scale_group.add_argument("--max-file-size", type=int, default=None, metavar="BYTES",
                            help="Skip files larger than N bytes (default: 512000 = 500KB)")
    scale_group.add_argument("--include", default=None, metavar="GLOBS",
                            help="Comma-separated include globs, e.g. 'src/**,lib/**'")
    scale_group.add_argument("--exclude", default=None, metavar="GLOBS",
                            help="Comma-separated exclude globs, e.g. 'generated/**,vendor/**'")
    scale_group.add_argument("--workers", type=int, default=None,
                            help="Parallel worker threads (default: auto based on Ollama pool size)")
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


if __name__ == "__main__":
    main()
