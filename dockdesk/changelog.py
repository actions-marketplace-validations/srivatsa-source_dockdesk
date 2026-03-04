"""
DockDesk Changelog & History System

Persists audit runs to JSONL for dashboard consumption.
"""

import os
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from rich.console import Console

console = Console()

DEFAULT_CHANGELOG_FILE = "audit_history.jsonl"


@dataclass
class AuditRunMetadata:
    """Metadata for a single audit run."""
    run_id: str
    timestamp: str
    workspace: str
    model: str
    model_tier: str
    total_loc: int
    
    # Timing
    duration_seconds: float
    
    # Scope
    files_discovered: int
    files_audited: int
    files_skipped: int
    
    # Results
    pass_count: int
    fail_count: int
    risk_distribution: Dict[str, int]  # {"HIGH": 2, "MEDIUM": 3, "LOW": 5}
    
    # Fixes
    fixes_available: int
    fixes_applied: int
    fixes_skipped: int
    
    # Context
    git_branch: Optional[str] = None
    git_commit: Optional[str] = None
    ci_mode: bool = False
    auto_tune_used: bool = False
    
    # Config snapshot
    config_snapshot: Optional[Dict[str, Any]] = None


@dataclass 
class FileAuditRecord:
    """Record for a single file audit within a run."""
    run_id: str
    file_path: str
    relative_path: str
    status: str  # PASS, FAIL, SKIP
    risk: str    # HIGH, MEDIUM, LOW
    summary: str
    has_fix: bool
    fix_applied: bool
    audit_duration_ms: int


def get_git_info(workspace: str) -> Dict[str, Optional[str]]:
    """Get current git branch and commit."""
    try:
        from git import Repo
        repo = Repo(workspace, search_parent_directories=True)
        return {
            "branch": repo.active_branch.name if not repo.head.is_detached else None,
            "commit": repo.head.commit.hexsha[:8] if repo.head.is_valid() else None
        }
    except Exception:
        return {"branch": None, "commit": None}


def generate_run_id() -> str:
    """Generate a unique run ID."""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    short_uuid = uuid.uuid4().hex[:6]
    return f"run_{timestamp}_{short_uuid}"


class ChangelogWriter:
    """Writes audit history to JSONL file."""
    
    def __init__(self, workspace: str, changelog_file: str = DEFAULT_CHANGELOG_FILE):
        self.workspace = workspace
        self.changelog_path = Path(workspace) / changelog_file
        self.run_id = generate_run_id()
        self.start_time = datetime.now()
        
    def write_run_metadata(self, metadata: AuditRunMetadata):
        """Write run metadata as a single line."""
        record = {
            "type": "run_metadata",
            **asdict(metadata)
        }
        self._append_record(record)
        
    def write_file_record(self, record: FileAuditRecord):
        """Write a file audit record."""
        data = {
            "type": "file_audit",
            **asdict(record)
        }
        self._append_record(data)
        
    def _append_record(self, record: Dict):
        """Append a record to the JSONL file."""
        try:
            with open(self.changelog_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record, default=str) + "\n")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not write to changelog: {e}[/yellow]")
    
    def finalize_run(
        self,
        audit_results: List[Dict],
        config: Any,
        files_discovered: int,
        model: str,
        model_tier: str = "unknown",
        total_loc: int = 0,
        fix_results: Optional[List] = None
    ) -> AuditRunMetadata:
        """
        Finalize the run and write complete metadata.
        
        Args:
            audit_results: List of audit result dicts
            config: DockDeskConfig instance
            files_discovered: Total files discovered
            model: Model name used
            model_tier: Model tier (small/medium/large)
            total_loc: Total lines of code
            fix_results: Optional list of fix results
            
        Returns:
            AuditRunMetadata instance
        """
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        # Calculate stats
        pass_count = sum(1 for r in audit_results if r.get("status") == "PASS")
        fail_count = sum(1 for r in audit_results if r.get("status") == "FAIL")
        skip_count = sum(1 for r in audit_results if r.get("status") == "SKIP")
        
        risk_distribution = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "UNKNOWN": 0}
        for r in audit_results:
            risk = r.get("risk", "UNKNOWN")
            if risk in risk_distribution:
                risk_distribution[risk] += 1
            else:
                risk_distribution["UNKNOWN"] += 1
        
        fixes_available = sum(1 for r in audit_results if r.get("fix"))
        fixes_applied = 0
        fixes_skipped = 0
        
        if fix_results:
            from .fixer import FixStatus
            fixes_applied = sum(1 for f in fix_results if f.status == FixStatus.APPLIED)
            fixes_skipped = sum(1 for f in fix_results if f.status == FixStatus.SKIPPED)
        
        git_info = get_git_info(self.workspace)
        
        metadata = AuditRunMetadata(
            run_id=self.run_id,
            timestamp=self.start_time.isoformat(),
            workspace=self.workspace,
            model=model,
            model_tier=model_tier,
            total_loc=total_loc,
            duration_seconds=round(duration, 2),
            files_discovered=files_discovered,
            files_audited=len(audit_results),
            files_skipped=files_discovered - len(audit_results),
            pass_count=pass_count,
            fail_count=fail_count,
            risk_distribution=risk_distribution,
            fixes_available=fixes_available,
            fixes_applied=fixes_applied,
            fixes_skipped=fixes_skipped,
            git_branch=git_info["branch"],
            git_commit=git_info["commit"],
            ci_mode=getattr(config, 'ci_mode', False),
            auto_tune_used=getattr(config, 'auto_tune', False),
            config_snapshot=config.to_dict() if hasattr(config, 'to_dict') else None
        )
        
        self.write_run_metadata(metadata)
        
        # Write individual file records
        for result in audit_results:
            file_path = result.get("file", "")
            try:
                relative_path = os.path.relpath(file_path, self.workspace)
            except ValueError:
                relative_path = file_path
                
            fix_applied = False
            if fix_results:
                for fr in fix_results:
                    if fr.file_path == file_path and fr.status.value == "applied":
                        fix_applied = True
                        break
            
            record = FileAuditRecord(
                run_id=self.run_id,
                file_path=file_path,
                relative_path=relative_path,
                status=result.get("status", "UNKNOWN"),
                risk=result.get("risk", "UNKNOWN"),
                summary=result.get("summary", "")[:500],  # Truncate long summaries
                has_fix=bool(result.get("fix")),
                fix_applied=fix_applied,
                audit_duration_ms=result.get("duration_ms", 0)
            )
            self.write_file_record(record)
        
        console.print(f"[dim]Changelog updated: {self.changelog_path}[/dim]")
        return metadata


class ChangelogReader:
    """Reads and queries audit history."""
    
    def __init__(self, changelog_path: str):
        self.changelog_path = Path(changelog_path)
        
    def read_all(self) -> List[Dict]:
        """Read all records from changelog."""
        if not self.changelog_path.exists():
            return []
        
        records = []
        with open(self.changelog_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return records
    
    def get_runs(self, limit: int = 50) -> List[AuditRunMetadata]:
        """Get run metadata records."""
        records = self.read_all()
        runs = [r for r in records if r.get("type") == "run_metadata"]
        
        # Sort by timestamp descending
        runs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        return runs[:limit]
    
    def get_run_details(self, run_id: str) -> Dict:
        """Get details for a specific run."""
        records = self.read_all()
        
        metadata = None
        file_records = []
        
        for r in records:
            if r.get("run_id") == run_id:
                if r.get("type") == "run_metadata":
                    metadata = r
                elif r.get("type") == "file_audit":
                    file_records.append(r)
        
        return {
            "metadata": metadata,
            "files": file_records
        }
    
    def get_stats_summary(self) -> Dict:
        """Get aggregate statistics across all runs."""
        runs = self.get_runs(limit=1000)
        
        if not runs:
            return {}
        
        total_audits = len(runs)
        total_files = sum(r.get("files_audited", 0) for r in runs)
        total_fixes = sum(r.get("fixes_applied", 0) for r in runs)
        
        # Risk trends
        risk_totals = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for run in runs:
            dist = run.get("risk_distribution", {})
            for risk, count in dist.items():
                if risk in risk_totals:
                    risk_totals[risk] += count
        
        # Model usage
        model_usage = {}
        for run in runs:
            model = run.get("model", "unknown")
            model_usage[model] = model_usage.get(model, 0) + 1
        
        # Average duration
        durations = [r.get("duration_seconds", 0) for r in runs if r.get("duration_seconds")]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        return {
            "total_audits": total_audits,
            "total_files_audited": total_files,
            "total_fixes_applied": total_fixes,
            "risk_totals": risk_totals,
            "model_usage": model_usage,
            "average_duration_seconds": round(avg_duration, 2),
            "first_audit": runs[-1].get("timestamp") if runs else None,
            "last_audit": runs[0].get("timestamp") if runs else None
        }
    
    def export_for_dashboard(self) -> Dict:
        """Export data in dashboard-friendly format."""
        runs = self.get_runs(limit=100)
        stats = self.get_stats_summary()
        
        # Timeline data
        timeline = []
        for run in runs:
            timeline.append({
                "date": run.get("timestamp", "")[:10],
                "pass": run.get("pass_count", 0),
                "fail": run.get("fail_count", 0),
                "skip": run.get("skip_count", 0),
                "fixes": run.get("fixes_applied", 0),
                "model": run.get("model", ""),
                "duration": run.get("duration_seconds", 0)
            })
        
        return {
            "stats": stats,
            "timeline": timeline,
            "recent_runs": runs[:10]
        }
