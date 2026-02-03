import os
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional
from rich.console import Console
from .state import AuditState
from .discovery import Discovery
from .utils import Visualizer, Guardrails
from .rag import CodeRetriever
from .merkle import build_merkle_tree, get_merkle_diff
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from langchain_core.output_parsers import JsonOutputParser

console = Console()
MERKLE_SNAPSHOT = "merkle_snapshot.json"

# Default model (can be overridden via config)
DEFAULT_MODEL = "qwen2.5-coder:3b"
DEFAULT_TEMPERATURE = 0.1

# Node: Discover Files (Updated for Merkle)
def discover_node(state: AuditState) -> AuditState:
    console.print("[bold blue]Step 1: Discovery[/bold blue]")
    discovery = Discovery(state["workspace_path"])
    code_files = discovery.find_code_files()
    docs = discovery.find_docs()
    
    # Store doc contents
    doc_sources = [
        {
            "path": d.path,
            "content": d.content,
            "type": d.doc_type
        } for d in docs
    ]
    
    return {
        "discovered_files": code_files,
        "doc_sources": doc_sources,
        "file_hashes": {}  # placeholder for backward compatibility
    }

# Node: Integrity Check (Merkle Tree)
def integrity_node(state: AuditState) -> AuditState:
    console.print("[bold blue]Step 2: Integrity Check (Git diff -> Merkle fallback)[/bold blue]")

    workspace = state["workspace_path"]

    def _git_changed_files(ws: str) -> List[str]:
        try:
            from git import Repo
            repo = Repo(ws, search_parent_directories=True)
            if repo.bare:
                return []

            candidates = ["origin/main", "origin/master", "main", "master"]
            diff_files: List[str] = []

            for target in candidates:
                try:
                    diff_out = repo.git.diff("--name-only", f"{target}...HEAD")
                    if diff_out.strip():
                        diff_files = diff_out.strip().splitlines()
                        break
                except Exception:
                    continue

            if not diff_files:
                try:
                    diff_out = repo.git.diff("--name-only")
                    diff_files = diff_out.strip().splitlines() if diff_out.strip() else []
                except Exception:
                    pass

            abs_paths = []
            ws_abs = os.path.abspath(repo.working_tree_dir or ws)
            for rel in diff_files:
                abs_p = os.path.abspath(os.path.join(ws_abs, rel))
                if abs_p.startswith(ws_abs) and os.path.isfile(abs_p):
                    abs_paths.append(abs_p)
            return abs_paths
        except Exception:
            return []

    # 1) Prefer Git diff scope
    git_changed = _git_changed_files(workspace)

    changed_files: List[str] = []
    file_contents = {}

    if git_changed:
        console.print(f"[yellow]Git diff scope: {len(git_changed)} file(s)[/yellow]")
        changed_files = git_changed
    else:
        # 2) Fallback to Merkle snapshot diff
        current_tree = build_merkle_tree(workspace)

        old_tree_dict = {}
        if os.path.exists(MERKLE_SNAPSHOT):
            try:
                with open(MERKLE_SNAPSHOT, 'r') as f:
                    old_tree_dict = json.load(f)
            except Exception:
                old_tree_dict = {}

        diffs = get_merkle_diff(old_tree_dict, current_tree)
        changed_files = diffs["modified"] + diffs["added"]

        if not changed_files and not diffs["removed"]:
            console.print("[green]No changes detected (Merkle snapshot matched).[/green]")
            return {"changed_files": [], "file_contents": {}}

        # Persist snapshot for next run
        try:
            with open(MERKLE_SNAPSHOT, 'w') as f:
                json.dump(current_tree.to_dict(), f)
        except Exception:
            pass

        console.print(f"[yellow]Merkle scope: {len(changed_files)} file(s)[/yellow]")

    # Load content for scoped files
    for fpath in changed_files:
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                file_contents[fpath] = f.read()
        except Exception:
            console.print(f"[red]Failed to read {fpath}[/red]")

    return {
        "changed_files": changed_files,
        "file_contents": file_contents
    }

# Node: RAG Retrieval
def retrieval_node(state: AuditState) -> AuditState:
    if not state["changed_files"]:
        return {"context_data": ""}

    console.print("[bold blue]Step 3: RAG Retrieval[/bold blue]")
    retriever = CodeRetriever()
    
    documents = []
    metadatas = []
    
    for path, content in state["file_contents"].items():
        documents.append(content)
        metadatas.append({"source": path})
        
    retriever.index_documents(documents, metadatas)
    
    query = "Authentication mechanisms, API routes, main entry points, security configurations"
    context = retriever.query(query)
    
    return {"context_data": context}

def parse_llm_json(content: str) -> dict:
    try:
        parser = JsonOutputParser()
        return parser.parse(content)
    except Exception:
        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            content = content.strip()
            return json.loads(content)
        except Exception:
            import re
            status_match = re.search(r'"status":\s*"([^"]+)"', content)
            risk_match = re.search(r'"risk":\s*"([^"]+)"', content)
            summary_match = re.search(r'"summary":\s*"([^"]+)"', content)
            fix_match = re.search(r'"fix":\s*"(.*)"', content, re.DOTALL)
            
            if status_match:
                return {
                    "status": status_match.group(1),
                    "risk": risk_match.group(1) if risk_match else "UNKNOWN",
                    "summary": summary_match.group(1) if summary_match else "Parsed via Regex",
                    "fix": fix_match.group(1) if fix_match else ""
                }
            raise


def _select_docs_for_file(file_path: str, doc_sources: List[dict], top_k: int = 3) -> List[dict]:
    """Pick a small, relevant doc subset to keep prompts lean."""
    if not doc_sources:
        return []

    base = os.path.basename(file_path).lower()
    scores = []
    for doc in doc_sources:
        path = doc.get("path", "").lower()
        score = 0
        if base and base in path:
            score += 2
        if os.path.dirname(file_path).lower() in path:
            score += 1
        # prefer smaller docs to keep token count low
        score -= len(doc.get("content", "")) / 5000.0
        scores.append((score, doc))

    scores.sort(key=lambda x: x[0], reverse=True)
    return [d for _, d in scores[:top_k]]

# Node: LLM Audit
def audit_node(state: AuditState) -> AuditState:
    if not state["changed_files"]:
        return {"audit_results": []}

    console.print("[bold blue]Step 4: LLM Audit[/bold blue]")

    audit_results: List[dict] = []
    changed_files = state["changed_files"]
    context_data = state.get("context_data", "")
    
    # Get model from state/config or use default
    model_name = state.get("model", DEFAULT_MODEL)
    config = state.get("config")
    temperature = config.temperature if config and hasattr(config, 'temperature') else DEFAULT_TEMPERATURE
    timeout = config.timeout_per_file if config and hasattr(config, 'timeout_per_file') else 120
    
    console.print(f"[dim]Using model: {model_name} (temp={temperature})[/dim]")

    def _audit_single(file_path: str) -> dict:
        start_time = time.time()
        code_content = state["file_contents"].get(file_path, "")
        docs_subset = _select_docs_for_file(file_path, state["doc_sources"], top_k=3)
        docs_text = "\n\n".join([f"--- DOC: {d['path']} ---\n{d['content']}" for d in docs_subset])

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a Senior Security & Code Auditor. 
            Analyze the CODE against the DOCUMENTATION.
            Keep responses concise.
            
            Output JSON only:
            {{
                "status": "PASS" | "FAIL",
                "risk": "HIGH" | "MEDIUM" | "LOW",
                "summary": "Short explanation",
                "fix": "Corrected markdown snippet for the documentation"
            }}
            """),
            ("user", """
            CONTEXT FROM KNOWLEDGE BASE:
            {context_data}
            
            TARGET FILE: {file_path}
            CODE CONTENT:
            {code_content}
            
            DOCUMENTATION (subset):
            {docs_text}
            """)
        ])

        llm_local = ChatOllama(model=model_name, temperature=temperature)
        chain = prompt | llm_local
        response = chain.invoke({
            "context_data": context_data,
            "file_path": file_path,
            "code_content": code_content,
            "docs_text": docs_text
        })
        content = response.content

        result = parse_llm_json(content)
        result["file"] = file_path
        result["fix"] = Guardrails.sanitize_fix(result.get("fix", ""))
        result["duration_ms"] = int((time.time() - start_time) * 1000)
        return result

    max_workers = min(4, len(changed_files)) if changed_files else 1
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(_audit_single, f): f for f in changed_files}
        for future in as_completed(future_map):
            fpath = future_map[future]
            try:
                res = future.result(timeout=timeout)
                audit_results.append(res)
            except Exception as e:
                console.print(f"[red]Audit failed for {fpath}: {e}[/red]")
                # Add failed result for tracking
                audit_results.append({
                    "file": fpath,
                    "status": "ERROR",
                    "risk": "UNKNOWN",
                    "summary": f"Audit failed: {str(e)}",
                    "fix": "",
                    "duration_ms": 0
                })

    return {"audit_results": audit_results}

# Node: Reporting
def reporting_node(state: AuditState) -> AuditState:
    console.print("[bold blue]Step 5: Reporting[/bold blue]")
    
    results = state.get("audit_results", [])
    changed = state.get("changed_files", [])
    config = state.get("config")
    model_name = state.get("model", DEFAULT_MODEL)
    model_tier = state.get("model_tier", "unknown")
    
    risk_map = {}
    for res in results:
        risk_map[res["file"]] = res.get("risk", "UNKNOWN")
        
    mermaid_graph = Visualizer.generate_mermaid_graph(changed, risk_map)
    
    # Calculate summary stats
    pass_count = sum(1 for r in results if r.get("status") == "PASS")
    fail_count = sum(1 for r in results if r.get("status") == "FAIL")
    error_count = sum(1 for r in results if r.get("status") == "ERROR")
    
    high_risk = sum(1 for r in results if r.get("risk") == "HIGH")
    medium_risk = sum(1 for r in results if r.get("risk") == "MEDIUM")
    low_risk = sum(1 for r in results if r.get("risk") == "LOW")
    
    # Build report
    report = f"""# 🛡️ DockDesk Audit Report

**Model:** {model_name} ({model_tier})  
**Files Audited:** {len(results)}  
**Status:** ✅ {pass_count} Pass | ❌ {fail_count} Fail | ⚠️ {error_count} Error

## Risk Distribution
| Level | Count |
|-------|-------|
| 🔴 HIGH | {high_risk} |
| 🟡 MEDIUM | {medium_risk} |
| 🟢 LOW | {low_risk} |

## Dependency Graph

{mermaid_graph}

## File Results

"""
    
    for res in results:
        status = res.get("status", "UNKNOWN")
        if status == "PASS":
            icon = "✅"
        elif status == "FAIL":
            icon = "❌"
        else:
            icon = "⚠️"
            
        risk = res.get("risk", "UNKNOWN")
        risk_badge = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(risk, "⚪")
        
        file_path = res.get("file", "unknown")
        try:
            rel_path = os.path.relpath(file_path, state["workspace_path"])
        except ValueError:
            rel_path = file_path
            
        report += f"### {icon} {rel_path}\n\n"
        report += f"**Risk:** {risk_badge} {risk}  \n"
        report += f"**Summary:** {res.get('summary', 'No summary')}\n\n"
        
        if res.get("fix"):
            report += f"<details>\n<summary>📝 Proposed Fix</summary>\n\n```markdown\n{res.get('fix')}\n```\n\n</details>\n\n"
        
        report += "---\n\n"
    
    report += f"\n> Generated by DockDesk Neural Auditor ({model_name})\n"
            
    with open("audit_report.md", "w", encoding="utf-8") as f:
        f.write(report)
    
    console.print(f"[green]Report written to audit_report.md[/green]")
    console.print(f"[dim]Results: {pass_count} pass, {fail_count} fail, {error_count} error[/dim]")
    console.print(f"[dim]Risk: {high_risk} HIGH, {medium_risk} MEDIUM, {low_risk} LOW[/dim]")
        
    return {"report_path": "audit_report.md", "mermaid_graph": mermaid_graph}
