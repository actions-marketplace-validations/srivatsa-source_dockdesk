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
from rich.console import Console
from rich.panel import Panel

console = Console()


def run_audit(args):
    """Run the main audit workflow."""
    from src.graph import create_audit_graph
    from src.config import build_config, OutputFormat, RiskLevel
    from src.models import (
        auto_select_model, validate_model, get_model_info,
        get_model_recommendation_message, count_lines_of_code, DEFAULT_MODEL
    )
    from src.changelog import ChangelogWriter
    from src.fixer import apply_fixes_batch
    
    # Build config from CLI args
    cli_args = {
        "workspace": args.workspace,
        "model": args.model,
        "auto_tune": args.auto_tune,
        "auto_fix": args.fix,
        "fix_code": args.fix_code,
        "ci_mode": args.ci,
        "verbose": args.verbose,
        "output_format": args.format,
        "output_file": args.output,
        "fail_on_risk": args.fail_on_risk,
        "skip_rag": args.skip_rag,
    }
    
    config = build_config(cli_args, args.workspace)
    workspace = config.workspace
    
    # Model selection
    model = config.model
    model_tier = "unknown"
    total_loc = count_lines_of_code(workspace)
    
    if config.auto_tune:
        model, reason = auto_select_model(workspace)
        console.print(f"[cyan]🧠 Auto-tuned model: {model} ({reason})[/cyan]")
        model_info = get_model_info(model)
        model_tier = model_info.tier.value if model_info else "unknown"
    else:
        # Validate selected model
        is_valid, message = validate_model(model, strict=False)
        if not is_valid:
            console.print(f"[red]{message}[/red]")
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
        f"[bold blue]DockDesk Semantic Auditor[/bold blue]\n"
        f"Workspace: {workspace}\n"
        f"Model: {model} ({model_tier})\n"
        f"LOC: {total_loc:,}",
        border_style="blue"
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
        "audit_results": [],
        "mermaid_graph": "",
        # New fields
        "config": config,
        "model": model,
        "model_tier": model_tier,
        "total_loc": total_loc,
    }
    
    try:
        result = app.invoke(initial_state)
        audit_results = result.get("audit_results", [])
        
        # Apply fixes if requested
        fix_results = None
        if config.auto_fix and audit_results:
            console.print("\n[bold]Applying fixes...[/bold]")
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
                console.print(f"[green]JSON report: {config.output_file}[/green]")
            else:
                print(json.dumps(json_output, indent=2, default=str))
                
        elif config.output_format == OutputFormat.SARIF:
            sarif_output = generate_sarif(audit_results, workspace)
            sarif_path = config.output_file or "audit_report.sarif"
            with open(sarif_path, 'w') as f:
                json.dump(sarif_output, f, indent=2)
            console.print(f"[green]SARIF report: {sarif_path}[/green]")
        else:
            console.print(f"\n[green]✓ Audit Complete. Report: {report_path}[/green]")
        
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
                console.print(f"[red]::error::Audit failed risk threshold ({config.fail_on_risk.value})[/red]")
                sys.exit(1)
                
    except Exception as e:
        console.print(f"[red]Audit Failed: {e}[/red]")
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
    from src.models import print_model_list
    print_model_list()


def init_config_cmd(args):
    """Initialize a sample configuration file."""
    from src.config import create_sample_config
    
    config_content = create_sample_config(args.workspace, format="yaml")
    config_path = os.path.join(args.workspace, "dockdesk.yml")
    
    if os.path.exists(config_path) and not args.force:
        console.print(f"[yellow]Config already exists: {config_path}[/yellow]")
        console.print("Use --force to overwrite")
        return
    
    with open(config_path, 'w') as f:
        f.write(config_content)
    
    console.print(f"[green]✓ Created config: {config_path}[/green]")


def dashboard_cmd(args):
    """Launch the dashboard or export data."""
    from src.changelog import ChangelogReader
    
    changelog_path = os.path.join(args.workspace, "audit_history.jsonl")
    
    if not os.path.exists(changelog_path):
        console.print("[yellow]No audit history found. Run an audit first.[/yellow]")
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
            f"[bold]DockDesk Audit Statistics[/bold]\n\n"
            f"Total Audits: {stats.get('total_audits', 0)}\n"
            f"Files Audited: {stats.get('total_files_audited', 0):,}\n"
            f"Fixes Applied: {stats.get('total_fixes_applied', 0)}\n"
            f"Avg Duration: {stats.get('average_duration_seconds', 0):.1f}s\n\n"
            f"[dim]Risk Distribution:[/dim]\n"
            f"  HIGH: {stats.get('risk_totals', {}).get('HIGH', 0)}\n"
            f"  MEDIUM: {stats.get('risk_totals', {}).get('MEDIUM', 0)}\n"
            f"  LOW: {stats.get('risk_totals', {}).get('LOW', 0)}\n\n"
            f"[dim]Use --export <file.json> to export for React dashboard[/dim]",
            border_style="cyan"
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
    parser.add_argument("--model", "-m", default=None, help="Ollama model to use (default: qwen2.5-coder:3b)")
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


if __name__ == "__main__":
    main()
