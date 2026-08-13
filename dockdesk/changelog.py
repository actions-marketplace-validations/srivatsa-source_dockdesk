"""
DockDesk Changelog & History System

Persists audit runs to JSONL for dashboard consumption.
"""

import os
import json
import uuid
from collections import defaultdict
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
    author: str = "Unknown"
    author_email: str = ""
    last_commit: str = ""
    team: str = ""


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
        self._init_sqlite()
        
    def _init_sqlite(self):
        db_path = os.path.join(self.workspace, ".dockdesk_cache.db")
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    timestamp TEXT,
                    workspace TEXT,
                    model TEXT,
                    model_tier TEXT,
                    total_loc INTEGER,
                    duration_seconds REAL,
                    files_discovered INTEGER,
                    files_audited INTEGER,
                    files_skipped INTEGER,
                    pass_count INTEGER,
                    fail_count INTEGER,
                    risk_distribution TEXT,
                    fixes_available INTEGER,
                    fixes_applied INTEGER,
                    fixes_skipped INTEGER,
                    git_branch TEXT,
                    git_commit TEXT,
                    ci_mode INTEGER,
                    auto_tune_used INTEGER,
                    config_snapshot TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS file_audits (
                    run_id TEXT,
                    file_path TEXT,
                    relative_path TEXT,
                    status TEXT,
                    risk TEXT,
                    summary TEXT,
                    has_fix INTEGER,
                    fix_applied INTEGER,
                    audit_duration_ms INTEGER,
                    author TEXT,
                    author_email TEXT,
                    last_commit TEXT,
                    team TEXT
                )
            """)
            conn.commit()
            conn.close()
        except Exception:
            pass

    def write_run_metadata(self, metadata: AuditRunMetadata):
        """Write run metadata as a single line."""
        record = {
            "type": "run_metadata",
            **asdict(metadata)
        }
        self._append_record(record)
        
        # SQLite persistence
        db_path = os.path.join(self.workspace, ".dockdesk_cache.db")
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO runs (
                    run_id, timestamp, workspace, model, model_tier, total_loc, duration_seconds,
                    files_discovered, files_audited, files_skipped, pass_count, fail_count,
                    risk_distribution, fixes_available, fixes_applied, fixes_skipped,
                    git_branch, git_commit, ci_mode, auto_tune_used, config_snapshot
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metadata.run_id, metadata.timestamp, metadata.workspace, metadata.model, metadata.model_tier,
                metadata.total_loc, metadata.duration_seconds, metadata.files_discovered, metadata.files_audited,
                metadata.files_skipped, metadata.pass_count, metadata.fail_count, json.dumps(metadata.risk_distribution),
                metadata.fixes_available, metadata.fixes_applied, metadata.fixes_skipped,
                metadata.git_branch, metadata.git_commit, 1 if metadata.ci_mode else 0,
                1 if metadata.auto_tune_used else 0, json.dumps(metadata.config_snapshot)
            ))
            conn.commit()
            conn.close()
        except Exception:
            pass
        
    def write_file_record(self, record: FileAuditRecord):
        """Write a file audit record."""
        data = {
            "type": "file_audit",
            **asdict(record)
        }
        self._append_record(data)
        
        # SQLite persistence
        db_path = os.path.join(self.workspace, ".dockdesk_cache.db")
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO file_audits (
                    run_id, file_path, relative_path, status, risk, summary,
                    has_fix, fix_applied, audit_duration_ms, author, author_email, last_commit, team
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.run_id, record.file_path, record.relative_path, record.status, record.risk, record.summary,
                1 if record.has_fix else 0, 1 if record.fix_applied else 0, record.audit_duration_ms,
                record.author, record.author_email, record.last_commit, record.team
            ))
            conn.commit()
            conn.close()
        except Exception:
            pass
        
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
                audit_duration_ms=result.get("duration_ms", 0),
                author=result.get("author", "Unknown"),
                author_email=result.get("author_email", ""),
                last_commit=result.get("last_commit", ""),
                team=result.get("team", "")
            )
            self.write_file_record(record)
        
        console.print(f"[dim]Changelog updated: {self.changelog_path}[/dim]")
        return metadata


class ChangelogReader:
    """Reads and queries audit history."""
    
    def __init__(self, changelog_path: str):
        self.changelog_path = Path(changelog_path)
        
    def read_all(self) -> List[Dict]:
        """Read all records from changelog, prioritizing SQLite and falling back to JSONL."""
        db_path = os.path.join(self.changelog_path.parent, ".dockdesk_cache.db")
        
        # 1. Try reading from SQLite first
        if os.path.exists(db_path):
            try:
                import sqlite3
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='runs'")
                if cursor.fetchone():
                    cursor.execute("SELECT * FROM runs")
                    runs_rows = cursor.fetchall()
                    run_cols = [col[0] for col in cursor.description]
                    
                    cursor.execute("SELECT * FROM file_audits")
                    audits_rows = cursor.fetchall()
                    audit_cols = [col[0] for col in cursor.description]
                    
                    conn.close()
                    
                    records = []
                    for row in runs_rows:
                        run_dict = dict(zip(run_cols, row))
                        run_dict["type"] = "run_metadata"
                        if run_dict.get("risk_distribution"):
                            try:
                                run_dict["risk_distribution"] = json.loads(run_dict["risk_distribution"])
                            except Exception:
                                pass
                        if run_dict.get("config_snapshot"):
                            try:
                                run_dict["config_snapshot"] = json.loads(run_dict["config_snapshot"])
                            except Exception:
                                pass
                        run_dict["ci_mode"] = bool(run_dict["ci_mode"])
                        run_dict["auto_tune_used"] = bool(run_dict["auto_tune_used"])
                        records.append(run_dict)
                        
                    for row in audits_rows:
                        audit_dict = dict(zip(audit_cols, row))
                        audit_dict["type"] = "file_audit"
                        audit_dict["has_fix"] = bool(audit_dict["has_fix"])
                        audit_dict["fix_applied"] = bool(audit_dict["fix_applied"])
                        records.append(audit_dict)
                        
                    if records:
                        return records
            except Exception:
                pass

        # 2. Fall back to JSONL file
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
                        
        # 3. Auto-migration to SQLite
        if records:
            try:
                self._init_sqlite_db_at(str(self.changelog_path.parent))
                import sqlite3
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                for r in records:
                    if r.get("type") == "run_metadata":
                        cursor.execute("""
                            INSERT OR REPLACE INTO runs (
                                run_id, timestamp, workspace, model, model_tier, total_loc, duration_seconds,
                                files_discovered, files_audited, files_skipped, pass_count, fail_count,
                                risk_distribution, fixes_available, fixes_applied, fixes_skipped,
                                git_branch, git_commit, ci_mode, auto_tune_used, config_snapshot
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            r.get("run_id"), r.get("timestamp"), r.get("workspace"), r.get("model"), r.get("model_tier"),
                            r.get("total_loc", 0), r.get("duration_seconds", 0.0), r.get("files_discovered", 0), r.get("files_audited", 0),
                            r.get("files_skipped", 0), r.get("pass_count", 0), r.get("fail_count", 0), json.dumps(r.get("risk_distribution", {})),
                            r.get("fixes_available", 0), r.get("fixes_applied", 0), r.get("fixes_skipped", 0),
                            r.get("git_branch"), r.get("git_commit"), 1 if r.get("ci_mode") else 0,
                            1 if r.get("auto_tune_used") else 0, json.dumps(r.get("config_snapshot", {}))
                        ))
                    elif r.get("type") == "file_audit":
                        cursor.execute("""
                            INSERT INTO file_audits (
                                run_id, file_path, relative_path, status, risk, summary,
                                has_fix, fix_applied, audit_duration_ms, author, author_email, last_commit, team
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            r.get("run_id"), r.get("file_path"), r.get("relative_path"), r.get("status"), r.get("risk"), r.get("summary"),
                            1 if r.get("has_fix") else 0, 1 if r.get("fix_applied") else 0, r.get("audit_duration_ms", 0),
                            r.get("author", "Unknown"), r.get("author_email", ""), r.get("last_commit", ""), r.get("team", "")
                        ))
                conn.commit()
                conn.close()
            except Exception:
                pass
                
        return records

    def _init_sqlite_db_at(self, workspace: str):
        db_path = os.path.join(workspace, ".dockdesk_cache.db")
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    timestamp TEXT,
                    workspace TEXT,
                    model TEXT,
                    model_tier TEXT,
                    total_loc INTEGER,
                    duration_seconds REAL,
                    files_discovered INTEGER,
                    files_audited INTEGER,
                    files_skipped INTEGER,
                    pass_count INTEGER,
                    fail_count INTEGER,
                    risk_distribution TEXT,
                    fixes_available INTEGER,
                    fixes_applied INTEGER,
                    fixes_skipped INTEGER,
                    git_branch TEXT,
                    git_commit TEXT,
                    ci_mode INTEGER,
                    auto_tune_used INTEGER,
                    config_snapshot TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS file_audits (
                    run_id TEXT,
                    file_path TEXT,
                    relative_path TEXT,
                    status TEXT,
                    risk TEXT,
                    summary TEXT,
                    has_fix INTEGER,
                    fix_applied INTEGER,
                    audit_duration_ms INTEGER,
                    author TEXT,
                    author_email TEXT,
                    last_commit TEXT,
                    team TEXT
                )
            """)
            conn.commit()
            conn.close()
        except Exception:
            pass
    
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

    @staticmethod
    def _normalize_status(value: Any) -> str:
        status = str(value or "UNKNOWN").upper()
        if status in {"PASS", "FAIL", "SKIP", "ERROR", "UNKNOWN"}:
            return status
        return "UNKNOWN"

    @staticmethod
    def _normalize_risk(value: Any) -> str:
        risk = str(value or "UNKNOWN").upper()
        if risk in {"HIGH", "MEDIUM", "LOW"}:
            return risk
        return "UNKNOWN"

    def _build_audit_tree(self, files: List[Dict[str, Any]], workspace: str) -> Dict[str, Any]:
        root = {
            "name": os.path.basename(workspace) or "root",
            "type": "dir",
            "children": [],
            "risk_counts": {"HIGH": 0, "MEDIUM": 0, "LOW": 0},
        }

        def ensure_dir(parent: Dict[str, Any], name: str) -> Dict[str, Any]:
            for child in parent.get("children", []):
                if child.get("type") == "dir" and child.get("name") == name:
                    return child
            node = {"name": name, "type": "dir", "children": [], "risk_counts": {"HIGH": 0, "MEDIUM": 0, "LOW": 0}}
            parent["children"].append(node)
            return node

        for record in files:
            rel = str(record.get("file", record.get("relative_path", "unknown"))).replace("\\", "/")
            parts = [p for p in rel.split("/") if p]
            if not parts:
                continue
            current = root
            for idx, part in enumerate(parts):
                if idx == len(parts) - 1:
                    current["children"].append({
                        "name": part,
                        "type": "file",
                        "path": rel,
                        "status": self._normalize_status(record.get("status")),
                        "risk": self._normalize_risk(record.get("risk")),
                        "safe_to_push": bool(record.get("safe_to_push", record.get("status") == "PASS")),
                        "summary": str(record.get("summary", "") or "")[:200],
                        "fix": str(record.get("fix", "") or "")[:300],
                        "reasoning": str(record.get("reasoning", "") or "")[:300],
                        "code_model": record.get("code_model", ""),
                        "reasoning_model": record.get("reasoning_model", ""),
                        "duration_ms": record.get("duration_ms", record.get("audit_duration_ms", 0)),
                    })
                else:
                    current = ensure_dir(current, part)

        # Populate directory risk counts from leaf nodes.
        def rollup(node: Dict[str, Any]) -> Dict[str, int]:
            counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
            for child in node.get("children", []):
                if child.get("type") == "file":
                    risk = self._normalize_risk(child.get("risk"))
                    if risk in counts:
                        counts[risk] += 1
                else:
                    child_counts = rollup(child)
                    for risk, amount in child_counts.items():
                        counts[risk] += amount
            node["risk_counts"] = counts
            return counts

        rollup(root)
        return root

    def export_for_dashboard(self) -> Dict:
        """Export data in dashboard-friendly format."""
        runs = self.get_runs(limit=100)
        stats = self.get_stats_summary()

        if not runs:
            return {
                "stats": stats,
                "timeline": [],
                "recent_runs": [],
                "latest_run_files": [],
                "audit_tree": {"name": "root", "type": "dir", "children": [], "risk_counts": {"HIGH": 0, "MEDIUM": 0, "LOW": 0}},
                "available_models": [],
                "models_used_this_run": [],
                "dual_model": {},
                "orchestration_metrics": {},
                "accountability": {"developers": {}, "teams": {}, "top_offenders": [], "clean_streaks": [], "codeowners_loaded": False},
                "audit_chain_link": {},
                "history": [],
                "latest": {
                    "metrics": {"files_analyzed": 0, "findings_count": 0, "safe_to_push": 0, "unsafe_to_push": 0},
                    "pass_fail_distribution": {"PASS": 0, "FAIL": 0},
                    "risk_distribution": {"HIGH": 0, "MEDIUM": 0, "LOW": 0},
                    "models_per_file": {},
                },
            }

        workspace = str(self.changelog_path.parent.resolve())
        records = self.read_all()
        latest_run = runs[0]
        latest_run_id = latest_run.get("run_id")
        latest_files = [r for r in records if r.get("type") == "file_audit" and r.get("run_id") == latest_run_id]

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
                "duration": run.get("duration_seconds", 0),
            })

        # Rebuild latest run file view from changelog records.
        latest_run_files = []
        latest_file_results = []
        models_per_file = {}
        for record in latest_files:
            rel = str(record.get("relative_path") or record.get("file_path") or "unknown").replace("\\", "/")
            file_path = str((Path(workspace) / rel).resolve()) if rel != "unknown" else rel
            status = self._normalize_status(record.get("status"))
            risk = self._normalize_risk(record.get("risk"))
            code_model = str(latest_run.get("model", ""))
            reasoning_model = str(latest_run.get("config_snapshot", {}).get("reasoning_model", "") or "")
            latest_run_files.append({
                "file": rel,
                "status": status,
                "risk": risk,
                "safe_to_push": risk == "LOW" or status == "PASS",
                "summary": str(record.get("summary", "") or "")[:200],
                "duration_ms": record.get("audit_duration_ms", 0),
                "code_model": code_model,
                "reasoning_model": reasoning_model,
                "author": record.get("author", "Unknown"),
                "author_email": record.get("author_email", ""),
                "last_commit": record.get("last_commit", ""),
                "team": record.get("team", ""),
            })
            latest_file_results.append({
                "file": file_path,
                "status": status,
                "risk": risk,
                "safe_to_push": risk == "LOW" or status == "PASS",
                "summary": str(record.get("summary", "") or "")[:200],
                "duration_ms": record.get("audit_duration_ms", 0),
                "code_model": code_model,
                "reasoning_model": reasoning_model,
            })
            if code_model:
                models_per_file[rel] = code_model

        # Use the same accountability and chain logic as a live audit run.
        try:
            from .accountability import build_accountability, build_audit_chain_link

            accountability = build_accountability(latest_file_results, workspace)
            audit_chain_link = build_audit_chain_link(latest_run_id or "dashboard", workspace, latest_file_results).to_dict()
        except Exception:
            accountability = {"developers": {}, "teams": {}, "top_offenders": [], "clean_streaks": [], "codeowners_loaded": False}
            audit_chain_link = {}

        config_snapshot = latest_run.get("config_snapshot") or {}
        available_models = sorted({m for m in [latest_run.get("model", ""), config_snapshot.get("reasoning_model", "")] if m})
        available_models = sorted(set(available_models).union(stats.get("model_usage", {}).keys()))

        orchestration_metrics = {
            "run_id": latest_run_id,
            "files_discovered": latest_run.get("files_discovered", 0),
            "files_analyzed": latest_run.get("files_audited", 0),
            "total_loc": latest_run.get("total_loc", 0),
            "total_duration_ms": int(float(latest_run.get("duration_seconds", 0)) * 1000),
            "avg_duration_ms": int((float(latest_run.get("duration_seconds", 0)) * 1000) / max(latest_run.get("files_audited", 1), 1)),
            "safe_to_push": sum(1 for f in latest_run_files if f.get("safe_to_push")),
            "unsafe_to_push": sum(1 for f in latest_run_files if not f.get("safe_to_push")),
            "models_per_file": models_per_file,
            "risk_distribution": latest_run.get("risk_distribution", {}),
            "pass_fail_distribution": {"PASS": latest_run.get("pass_count", 0), "FAIL": latest_run.get("fail_count", 0)},
        }

        code_model = latest_run.get("model", "")
        reasoning_model = config_snapshot.get("reasoning_model", "")

        # Compute CI/CD Pipeline Monitoring metrics
        ci_runs = [r for r in runs if r.get("ci_mode") or r.get("ci")]
        ci_count = len(ci_runs)
        ci_successes = sum(1 for r in ci_runs if r.get("fail_count", 0) == 0)
        ci_success_rate = int((ci_successes / ci_count * 100)) if ci_count > 0 else 100
        ci_avg_duration = round(sum(r.get("duration_seconds", 0.0) for r in ci_runs) / max(ci_count, 1), 2)
        
        pipeline_monitoring = {
            "total_runs": ci_count,
            "success_rate": ci_success_rate,
            "average_duration": ci_avg_duration,
            "runs": [
                {
                    "run_id": r.get("run_id"),
                    "timestamp": r.get("timestamp"),
                    "branch": r.get("git_branch", "main"),
                    "commit": r.get("git_commit", "N/A"),
                    "status": "PASS" if r.get("fail_count", 0) == 0 else "FAIL",
                    "pass_count": r.get("pass_count", 0),
                    "fail_count": r.get("fail_count", 0),
                    "duration": r.get("duration_seconds", 0.0),
                    "model": r.get("model", ""),
                } for r in ci_runs[:15]
            ]
        }

        return {
            "stats": stats,
            "timeline": timeline,
            "recent_runs": runs[:10],
            "latest_run_files": latest_run_files,
            "audit_tree": self._build_audit_tree(latest_file_results, workspace),
            "available_models": available_models,
            "models_used_this_run": [m for m in [code_model, reasoning_model] if m],
            "dual_model": {"code_model": code_model, "reasoning_model": reasoning_model} if code_model or reasoning_model else {},
            "orchestration_metrics": orchestration_metrics,
            "accountability": accountability,
            "audit_chain_link": audit_chain_link,
            "history": records,
            "pipeline_monitoring": pipeline_monitoring,
            "latest": {
                "metrics": {
                    "files_analyzed": latest_run.get("files_audited", 0),
                    "findings_count": len(latest_file_results),
                    "safe_to_push": orchestration_metrics["safe_to_push"],
                    "unsafe_to_push": orchestration_metrics["unsafe_to_push"],
                },
                "pass_fail_distribution": {"PASS": latest_run.get("pass_count", 0), "FAIL": latest_run.get("fail_count", 0)},
                "risk_distribution": {"HIGH": latest_run.get("risk_distribution", {}).get("HIGH", 0), "MEDIUM": latest_run.get("risk_distribution", {}).get("MEDIUM", 0), "LOW": latest_run.get("risk_distribution", {}).get("LOW", 0)},
                "models_per_file": models_per_file,
            },
        }
