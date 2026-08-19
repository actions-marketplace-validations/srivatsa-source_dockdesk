"""Repository knowledge graph generation for DockDesk.

Builds a static repository graph that can be rendered in the dashboard,
exported as JSON for LLM context, or published as a standalone artifact.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from rich.console import Console

from .dependency import build_dependency_graphs

console = Console(highlight=False)

_SKIP_DIRS = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "legacy",
    "node_modules",
    "target",
    "venv",
}

_SOURCE_EXTENSIONS = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".go",
    ".h",
    ".hpp",
    ".java",
    ".jsx",
    ".kt",
    ".py",
    ".rs",
    ".ts",
    ".tsx",
}

_DOC_EXTENSIONS = {".md", ".rst", ".txt", ".adoc"}
_CONFIG_EXTENSIONS = {".json", ".toml", ".yml", ".yaml", ".ini", ".cfg", ".env"}


def _is_skipped_directory(path: Path) -> bool:
    return any(part in _SKIP_DIRS for part in path.parts)


def _file_kind(path: Path) -> Tuple[str, str]:
    suffix = path.suffix.lower()
    if suffix == ".py":
        return "source", "python"
    if suffix in {".js", ".jsx"}:
        return "source", "javascript"
    if suffix in {".ts", ".tsx"}:
        return "source", "typescript"
    if suffix == ".java":
        return "source", "java"
    if suffix == ".cs":
        return "source", "dotnet"
    if suffix == ".go":
        return "source", "go"
    if suffix == ".rs":
        return "source", "rust"
    if suffix in _DOC_EXTENSIONS:
        return "doc", "markdown" if suffix == ".md" else "documentation"
    if suffix in _CONFIG_EXTENSIONS:
        return "config", "config"
    return "asset", suffix.lstrip(".") or "file"


def _node_id(prefix: str, relative_path: str) -> str:
    return f"{prefix}:{relative_path}".replace("\\", "/")


def _iter_repo_files(root: Path) -> Iterable[Path]:
    for current_root, dirs, files in os.walk(root):
        current = Path(current_root)
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")]
        if _is_skipped_directory(current):
            continue
        for file_name in files:
            file_path = current / file_name
            if _is_skipped_directory(file_path):
                continue
            yield file_path


def _ensure_directory_node(nodes: Dict[str, Dict[str, Any]], root_name: str, rel_dir: str) -> Dict[str, Any]:
    node_key = _node_id("dir", rel_dir)
    if node_key not in nodes:
        depth = len([part for part in rel_dir.split("/") if part])
        label = rel_dir.split("/")[-1] if rel_dir else root_name
        nodes[node_key] = {
            "id": node_key,
            "label": label,
            "path": rel_dir or ".",
            "kind": "directory",
            "group": rel_dir.split("/")[0] if rel_dir else root_name,
            "depth": depth,
            "language": "",
            "summary": "Directory cluster",
        }
    return nodes[node_key]


def build_knowledge_graph(workspace: str) -> Dict[str, Any]:
    """Build a static repository knowledge graph."""

    root = Path(workspace).resolve()
    if not root.exists():
        return {
            "workspace": str(root),
            "generated_at": datetime.utcnow().isoformat(),
            "nodes": [],
            "edges": [],
            "clusters": [],
            "stats": {
                "total_nodes": 0,
                "total_edges": 0,
                "file_nodes": 0,
                "directory_nodes": 0,
                "doc_nodes": 0,
                "source_nodes": 0,
                "config_nodes": 0,
                "entry_points": [],
            },
        }

    nodes: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []
    clusters: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"id": "", "label": "", "nodes": [], "kind": "cluster"})

    root_name = root.name or "workspace"
    root_id = _node_id("workspace", root_name)
    nodes[root_id] = {
        "id": root_id,
        "label": root_name,
        "path": ".",
        "kind": "workspace",
        "group": root_name,
        "depth": 0,
        "language": "",
        "summary": "Repository root",
    }

    for file_path in _iter_repo_files(root):
        try:
            relative_path = file_path.relative_to(root).as_posix()
        except ValueError:
            relative_path = file_path.as_posix()

        parent = file_path.parent
        parent_parts: List[str] = []
        if parent != root:
            try:
                parent_parts = list(parent.relative_to(root).parts)
            except ValueError:
                parent_parts = []

        current_dir_rel = ""
        current_parent_id = root_id
        for part in parent_parts:
            current_dir_rel = f"{current_dir_rel}/{part}".strip("/")
            dir_node = _ensure_directory_node(nodes, root_name, current_dir_rel)
            dir_id = dir_node["id"]
            if not any(edge["source"] == current_parent_id and edge["target"] == dir_id for edge in edges):
                edges.append({"source": current_parent_id, "target": dir_id, "kind": "contains"})
            current_parent_id = dir_id
            cluster_id = current_dir_rel.split("/")[0] if current_dir_rel else root_name
            clusters[cluster_id]["id"] = cluster_id
            clusters[cluster_id]["label"] = cluster_id
            if dir_id not in clusters[cluster_id]["nodes"]:
                clusters[cluster_id]["nodes"].append(dir_id)

        file_kind, language = _file_kind(file_path)
        file_id = _node_id("file", relative_path)
        try:
            size = file_path.stat().st_size
        except OSError:
            size = 0

        depth = len([part for part in relative_path.split("/") if part])
        node = {
            "id": file_id,
            "label": file_path.name,
            "path": relative_path,
            "kind": file_kind,
            "group": relative_path.split("/")[0] if "/" in relative_path else root_name,
            "depth": depth,
            "language": language,
            "size": size,
            "summary": f"{file_kind.title()} file",
        }
        nodes[file_id] = node

        if not any(edge["source"] == current_parent_id and edge["target"] == file_id for edge in edges):
            edges.append({"source": current_parent_id, "target": file_id, "kind": "contains"})

        cluster_id = relative_path.split("/")[0] if "/" in relative_path else root_name
        clusters[cluster_id]["id"] = cluster_id
        clusters[cluster_id]["label"] = cluster_id
        if file_id not in clusters[cluster_id]["nodes"]:
            clusters[cluster_id]["nodes"].append(file_id)

    try:
        forward_graph, _ = build_dependency_graphs(str(root))
        for source_file, dependencies in forward_graph.items():
            try:
                source_rel = Path(source_file).resolve().relative_to(root).as_posix()
            except Exception:
                continue
            source_id = _node_id("file", source_rel)
            if source_id not in nodes:
                continue
            for dependency in dependencies:
                try:
                    dependency_rel = Path(dependency).resolve().relative_to(root).as_posix()
                except Exception:
                    continue
                target_id = _node_id("file", dependency_rel)
                if target_id not in nodes:
                    continue
                edge = {"source": source_id, "target": target_id, "kind": "imports"}
                if edge not in edges:
                    edges.append(edge)
    except Exception:
        pass

    incoming = defaultdict(int)
    outgoing = defaultdict(int)
    for edge in edges:
        outgoing[edge["source"]] += 1
        incoming[edge["target"]] += 1

    for node_id, node in nodes.items():
        node["incoming"] = incoming.get(node_id, 0)
        node["outgoing"] = outgoing.get(node_id, 0)
        node["degree"] = node["incoming"] + node["outgoing"]

    file_nodes = [node for node in nodes.values() if node["kind"] not in {"directory", "workspace"}]
    directory_nodes = [node for node in nodes.values() if node["kind"] == "directory"]
    doc_nodes = [node for node in file_nodes if node["kind"] == "doc"]
    source_nodes = [node for node in file_nodes if node["kind"] == "source"]
    config_nodes = [node for node in file_nodes if node["kind"] == "config"]
    entry_points = sorted(
        [node["path"] for node in source_nodes if node.get("incoming", 0) == 0 and node.get("outgoing", 0) > 0],
        key=lambda value: (value.count("/"), value),
    )[:12]

    for cluster_id, cluster in clusters.items():
        cluster.setdefault("id", cluster_id)
        cluster.setdefault("label", cluster_id)
        cluster.setdefault("nodes", [])

    return {
        "workspace": str(root),
        "generated_at": datetime.utcnow().isoformat(),
        "nodes": list(nodes.values()),
        "edges": edges,
        "clusters": list(clusters.values()),
        "stats": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "file_nodes": len(file_nodes),
            "directory_nodes": len(directory_nodes),
            "doc_nodes": len(doc_nodes),
            "source_nodes": len(source_nodes),
            "config_nodes": len(config_nodes),
            "entry_points": entry_points,
        },
    }


def build_knowledge_graph_summary(graph: Dict[str, Any]) -> str:
    """Render a compact Markdown summary for the knowledge graph."""

    stats = graph.get("stats", {})
    clusters = graph.get("clusters", [])
    lines = ["# DockDesk Knowledge Graph", "", f"**Workspace:** `{graph.get('workspace', '')}`", ""]
    lines.append("## Overview")
    lines.append(f"- Nodes: {stats.get('total_nodes', 0)}")
    lines.append(f"- Edges: {stats.get('total_edges', 0)}")
    lines.append(f"- Files: {stats.get('file_nodes', 0)}")
    lines.append(f"- Directories: {stats.get('directory_nodes', 0)}")
    lines.append(f"- Source files: {stats.get('source_nodes', 0)}")
    lines.append(f"- Docs: {stats.get('doc_nodes', 0)}")
    lines.append("")

    entry_points = stats.get("entry_points", [])
    if entry_points:
        lines.append("## Entry Points")
        for item in entry_points:
            lines.append(f"- `{item}`")
        lines.append("")

    if clusters:
        lines.append("## Clusters")
        for cluster in sorted(clusters, key=lambda item: str(item.get("label", "")).lower()):
            node_count = len(cluster.get("nodes", []))
            lines.append(f"- `{cluster.get('label', 'cluster')}`: {node_count} node(s)")
        lines.append("")

    lines.append("> Generated by DockDesk knowledge-graph export")
    return "\n".join(lines)


def build_graph_dashboard_payload(workspace: str, graph: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build a minimal dashboard payload that still renders the graph view."""

    graph_data = graph or build_knowledge_graph(workspace)
    return {
        "stats": {
            "total_audits": 0,
            "total_files_audited": 0,
            "total_fixes_applied": 0,
            "risk_totals": {"HIGH": 0, "MEDIUM": 0, "LOW": 0},
            "model_usage": {},
            "average_duration_seconds": 0,
            "first_audit": None,
            "last_audit": None,
        },
        "timeline": [],
        "recent_runs": [],
        "latest_run_files": [],
        "audit_tree": {"name": Path(workspace).name or "root", "type": "dir", "children": [], "risk_counts": {"HIGH": 0, "MEDIUM": 0, "LOW": 0}},
        "available_models": [],
        "models_used_this_run": [],
        "dual_model": {},
        "orchestration_metrics": {"graph_only": True, "graph_nodes": graph_data.get("stats", {}).get("total_nodes", 0)},
        "accountability": {"developers": {}, "teams": {}, "top_offenders": [], "clean_streaks": [], "codeowners_loaded": False},
        "audit_chain_link": {},
        "history": [],
        "latest": {
            "metrics": {"files_analyzed": 0, "findings_count": 0, "safe_to_push": 0, "unsafe_to_push": 0},
            "pass_fail_distribution": {"PASS": 0, "FAIL": 0},
            "risk_distribution": {"HIGH": 0, "MEDIUM": 0, "LOW": 0},
            "models_per_file": {},
        },
        "knowledge_graph": graph_data,
    }


def write_knowledge_graph_outputs(
    workspace: str,
    output_path: str,
    markdown_path: Optional[str] = None,
    dashboard_data_path: Optional[str] = None,
) -> Dict[str, str]:
    """Write graph JSON and optional Markdown / dashboard exports to disk."""

    graph = build_knowledge_graph(workspace)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(graph, indent=2, default=str), encoding="utf-8")

    written = {"graph_path": str(output)}

    if markdown_path:
        markdown = Path(markdown_path)
        markdown.parent.mkdir(parents=True, exist_ok=True)
        markdown.write_text(build_knowledge_graph_summary(graph), encoding="utf-8")
        written["markdown_path"] = str(markdown)

    if dashboard_data_path:
        dashboard = Path(dashboard_data_path)
        dashboard.parent.mkdir(parents=True, exist_ok=True)
        dashboard.write_text(json.dumps(build_graph_dashboard_payload(workspace, graph), indent=2, default=str), encoding="utf-8")
        written["dashboard_data_path"] = str(dashboard)

    return written