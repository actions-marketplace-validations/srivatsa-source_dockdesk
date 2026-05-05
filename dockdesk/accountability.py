"""
DockDesk Accountability Engine - Per-Developer Drift Tracking.

The core USP module. Tracks who introduced drift, calculates per-developer
drift scores, and integrates with CODEOWNERS for team-level accountability.

This runs as a LangGraph node between reasoning and reporting.
"""

import os
import re
import hashlib
import json
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from rich.console import Console

console = Console(highlight=False)

# Risk weights for drift score calculation
RISK_WEIGHTS = {"HIGH": 10, "MEDIUM": 3, "LOW": 1}


@dataclass
class DeveloperProfile:
    """Accountability profile for a single developer."""
    name: str
    email: str = ""
    files_authored: int = 0
    files_passed: int = 0
    files_failed: int = 0
    files_skipped: int = 0
    high_risk_count: int = 0
    medium_risk_count: int = 0
    low_risk_count: int = 0
    drift_score: float = 0.0  # Higher = worse
    unsafe_push_count: int = 0
    files: List[str] = field(default_factory=list)
    team: str = ""

    def calculate_drift_score(self) -> float:
        """Calculate drift score: (risk-weighted failures) / total authored."""
        if self.files_authored == 0:
            return 0.0
        weighted = (
            self.high_risk_count * RISK_WEIGHTS["HIGH"]
            + self.medium_risk_count * RISK_WEIGHTS["MEDIUM"]
            + self.low_risk_count * RISK_WEIGHTS["LOW"]
        )
        self.drift_score = round(weighted / self.files_authored, 2)
        return self.drift_score

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AuditChainLink:
    """Single link in the tamper-evident audit chain."""
    run_id: str
    timestamp: str
    workspace: str
    files_audited: int
    risk_distribution: Dict[str, int]
    content_hash: str  # SHA-256 of this run's results
    previous_hash: str  # Hash of the previous link (Merkle chain)
    chain_hash: str = ""  # Hash of (previous_hash + content_hash)

    def compute_chain_hash(self) -> str:
        combined = f"{self.previous_hash}:{self.content_hash}"
        self.chain_hash = hashlib.sha256(combined.encode()).hexdigest()
        return self.chain_hash

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def git_blame_file(file_path: str, workspace: str) -> Dict[str, Any]:
    """Extract git blame info for a file: primary author, last commit, date."""
    result = {
        "author": "Unknown",
        "email": "",
        "last_commit": "",
        "last_date": "",
        "contributors": [],
    }

    try:
        blame_out = subprocess.check_output(
            ["git", "blame", "--porcelain", file_path],
            cwd=workspace,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=10,
        )

        authors: Dict[str, int] = {}
        emails: Dict[str, str] = {}
        current_author = ""

        for line in blame_out.split("\n"):
            if line.startswith("author "):
                current_author = line[7:].strip()
                authors[current_author] = authors.get(current_author, 0) + 1
            elif line.startswith("author-mail "):
                email = line[12:].strip().strip("<>")
                if current_author:
                    emails[current_author] = email

        if authors:
            # Primary author = most lines
            primary = max(authors, key=authors.get)
            result["author"] = primary
            result["email"] = emails.get(primary, "")
            result["contributors"] = sorted(
                [{"name": a, "lines": c, "email": emails.get(a, "")}
                 for a, c in authors.items()],
                key=lambda x: x["lines"],
                reverse=True,
            )

        # Get last commit info
        log_out = subprocess.check_output(
            ["git", "log", "-1", "--format=%H|%ai|%an", "--", file_path],
            cwd=workspace,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=10,
        ).strip()

        if log_out and "|" in log_out:
            parts = log_out.split("|", 2)
            result["last_commit"] = parts[0][:12]
            result["last_date"] = parts[1][:10]
            if not result["author"] or result["author"] == "Unknown":
                result["author"] = parts[2] if len(parts) > 2 else "Unknown"

    except Exception:
        pass

    return result


def parse_codeowners(workspace: str) -> Dict[str, str]:
    """Parse CODEOWNERS file to map file patterns to teams/owners.

    Returns dict mapping glob pattern → owner string.
    """
    owners: Dict[str, str] = {}
    codeowners_paths = [
        os.path.join(workspace, "CODEOWNERS"),
        os.path.join(workspace, ".github", "CODEOWNERS"),
        os.path.join(workspace, "docs", "CODEOWNERS"),
    ]

    for path in codeowners_paths:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split()
                    if len(parts) >= 2:
                        pattern = parts[0]
                        owner = " ".join(parts[1:])
                        owners[pattern] = owner
            break  # Use first found
        except Exception:
            continue

    return owners


def match_codeowner(file_path: str, owners: Dict[str, str]) -> str:
    """Match a file path against CODEOWNERS patterns. Returns owner or ''."""
    import fnmatch

    rel = file_path.replace("\\", "/")
    matched_owner = ""

    for pattern, owner in owners.items():
        # CODEOWNERS patterns: *.js, /src/**, etc.
        normalized = pattern.lstrip("/")
        if fnmatch.fnmatch(rel, normalized) or fnmatch.fnmatch(rel, f"**/{normalized}"):
            matched_owner = owner  # Last match wins (CODEOWNERS convention)

    return matched_owner


def build_accountability(
    audit_results: List[Dict],
    workspace: str,
) -> Dict[str, Any]:
    """Build per-developer accountability data from audit results.

    Returns:
        {
            "developers": {name: DeveloperProfile.to_dict()},
            "teams": {team: {members: [...], aggregate_drift: float}},
            "top_offenders": [...],
            "clean_streaks": [...],
            "codeowners_loaded": bool,
        }
    """
    developers: Dict[str, DeveloperProfile] = {}
    codeowners = parse_codeowners(workspace)

    for result in audit_results:
        file_path = result.get("file", "unknown")
        try:
            rel_path = os.path.relpath(file_path, workspace)
        except ValueError:
            rel_path = file_path

        # Get blame info
        blame = git_blame_file(rel_path, workspace)
        author = blame.get("author", "Unknown")
        email = blame.get("email", "")

        # Enrich the audit result with accountability data
        result["author"] = author
        result["author_email"] = email
        result["last_commit"] = blame.get("last_commit", "")
        result["last_date"] = blame.get("last_date", "")
        result["contributors"] = blame.get("contributors", [])

        # Match CODEOWNERS
        team = match_codeowner(rel_path, codeowners)
        result["team"] = team

        # Build developer profile
        if author not in developers:
            developers[author] = DeveloperProfile(name=author, email=email)

        dev = developers[author]
        dev.files_authored += 1
        dev.files.append(rel_path)
        if team:
            dev.team = team

        status = result.get("status", "UNKNOWN")
        risk = result.get("risk", "UNKNOWN")

        if status == "PASS":
            dev.files_passed += 1
        elif status == "FAIL":
            dev.files_failed += 1
            if risk == "HIGH":
                dev.high_risk_count += 1
            elif risk == "MEDIUM":
                dev.medium_risk_count += 1
            elif risk == "LOW":
                dev.low_risk_count += 1
        elif status == "SKIP":
            dev.files_skipped += 1

        if result.get("safe_to_push") is False:
            dev.unsafe_push_count += 1

    # Calculate drift scores
    for dev in developers.values():
        dev.calculate_drift_score()

    # Build team aggregation
    teams: Dict[str, Dict[str, Any]] = {}
    for dev in developers.values():
        team_name = dev.team or "unassigned"
        if team_name not in teams:
            teams[team_name] = {"members": [], "total_drift": 0.0, "file_count": 0}
        teams[team_name]["members"].append(dev.name)
        teams[team_name]["total_drift"] += dev.drift_score
        teams[team_name]["file_count"] += dev.files_authored

    for team_data in teams.values():
        member_count = len(team_data["members"])
        team_data["aggregate_drift"] = round(
            team_data["total_drift"] / max(member_count, 1), 2
        )

    # Rankings
    sorted_devs = sorted(developers.values(), key=lambda d: d.drift_score, reverse=True)
    top_offenders = [
        {"name": d.name, "drift_score": d.drift_score, "high_risk": d.high_risk_count}
        for d in sorted_devs[:5]
        if d.drift_score > 0
    ]

    clean_streaks = [
        {"name": d.name, "files_passed": d.files_passed, "files_authored": d.files_authored}
        for d in sorted_devs
        if d.drift_score == 0 and d.files_authored > 0
    ]

    return {
        "developers": {name: dev.to_dict() for name, dev in developers.items()},
        "teams": teams,
        "top_offenders": top_offenders,
        "clean_streaks": clean_streaks,
        "codeowners_loaded": bool(codeowners),
    }


def build_audit_chain_link(
    run_id: str,
    workspace: str,
    audit_results: List[Dict],
    chain_file: str = ".dockdesk_audit_chain.json",
) -> AuditChainLink:
    """Create a new tamper-evident link in the audit chain.

    Each link hashes (previous_hash + current_content_hash) to form a
    Merkle chain. Any deletion or modification of a past audit breaks the chain.
    """
    # Load existing chain
    chain_path = os.path.join(workspace, chain_file)
    previous_hash = "genesis"

    try:
        if os.path.exists(chain_path):
            with open(chain_path, "r", encoding="utf-8") as f:
                chain = json.load(f)
            if chain and isinstance(chain, list) and len(chain) > 0:
                previous_hash = chain[-1].get("chain_hash", "genesis")
        else:
            chain = []
    except Exception:
        chain = []

    # Hash current results
    results_json = json.dumps(audit_results, sort_keys=True, default=str)
    content_hash = hashlib.sha256(results_json.encode()).hexdigest()

    risk_dist = {
        "HIGH": sum(1 for r in audit_results if r.get("risk") == "HIGH"),
        "MEDIUM": sum(1 for r in audit_results if r.get("risk") == "MEDIUM"),
        "LOW": sum(1 for r in audit_results if r.get("risk") == "LOW"),
    }

    link = AuditChainLink(
        run_id=run_id,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        workspace=os.path.basename(workspace),
        files_audited=len(audit_results),
        risk_distribution=risk_dist,
        content_hash=content_hash,
        previous_hash=previous_hash,
    )
    link.compute_chain_hash()

    # Append to chain
    chain.append(link.to_dict())

    # Keep last 500 links to prevent unbounded growth
    if len(chain) > 500:
        chain = chain[-500:]

    try:
        with open(chain_path, "w", encoding="utf-8") as f:
            json.dump(chain, f, indent=2)
    except Exception as e:
        console.print(f"[yellow]Could not persist audit chain: {e}[/yellow]")

    return link


def verify_audit_chain(
    workspace: str,
    chain_file: str = ".dockdesk_audit_chain.json",
) -> Dict[str, Any]:
    """Verify the integrity of the audit chain.

    Returns:
        {"valid": bool, "total_links": int, "broken_at": int or None, "details": str}
    """
    chain_path = os.path.join(workspace, chain_file)

    if not os.path.exists(chain_path):
        return {"valid": True, "total_links": 0, "broken_at": None, "details": "No audit chain found."}

    try:
        with open(chain_path, "r", encoding="utf-8") as f:
            chain = json.load(f)
    except Exception as e:
        return {"valid": False, "total_links": 0, "broken_at": 0, "details": f"Chain file corrupt: {e}"}

    if not chain:
        return {"valid": True, "total_links": 0, "broken_at": None, "details": "Empty chain."}

    # Verify each link
    for i, link in enumerate(chain):
        expected_prev = "genesis" if i == 0 else chain[i - 1].get("chain_hash", "")
        actual_prev = link.get("previous_hash", "")

        if actual_prev != expected_prev:
            return {
                "valid": False,
                "total_links": len(chain),
                "broken_at": i,
                "details": f"Chain broken at link {i} (run {link.get('run_id', '?')}): "
                           f"expected prev_hash={expected_prev[:16]}..., got {actual_prev[:16]}...",
            }

        # Verify chain_hash integrity
        combined = f"{link.get('previous_hash', '')}:{link.get('content_hash', '')}"
        expected_chain = hashlib.sha256(combined.encode()).hexdigest()
        if link.get("chain_hash", "") != expected_chain:
            return {
                "valid": False,
                "total_links": len(chain),
                "broken_at": i,
                "details": f"Chain hash mismatch at link {i} (run {link.get('run_id', '?')})",
            }

    return {
        "valid": True,
        "total_links": len(chain),
        "broken_at": None,
        "details": f"Chain verified: {len(chain)} links, integrity OK.",
    }
