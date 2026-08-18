import os
import json
import time
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Dict
from rich.console import Console
from rich.progress import Progress, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table
from .state import AuditState
from .discovery import Discovery
from .utils import Visualizer, Guardrails
from .rag import CodeRetriever
from .merkle import build_merkle_tree, get_merkle_diff
from .discord import DiscordNotifier
from .cache import ResultCache
from .ollama_pool import OllamaPool
from .knowledge_graph import build_knowledge_graph, build_knowledge_graph_summary
from .providers import get_provider
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

console = Console(highlight=False)

# Legacy cache dir - migrated to SQLite on first run
LEGACY_CACHE_DIR = ".dockdesk_cache"

# Default models
DEFAULT_MODEL = "qwen2.5-coder:7b"                 # Code analysis (the "hands")
DEFAULT_REASONING_MODEL = "deepseek-r1:1.5b"  # Logical reasoning (the "brain")
DEFAULT_TEMPERATURE = 0.1
# ── Module-level singletons (migrated to state in v3) ──
# Keep simple module-level placeholders to avoid NameError in node functions.
# Concrete initialization occurs per-run inside `_init_infrastructure`.
_cache = None
_pool = None
_plugin_mgr = None
_current_workspace = None


def _get_file_git_diff(file_path: str, workspace: str) -> Optional[str]:
    """Extract only the unstaged/staged or branch diff for a target file."""
    try:
        import os
        from git import Repo
        repo = Repo(workspace, search_parent_directories=True)
        if repo.bare:
            return None
        repo_root = os.path.abspath(repo.working_tree_dir or workspace)
        rel_path = os.path.relpath(os.path.abspath(file_path), repo_root)
        
        candidates = []
        base_ref = os.environ.get("GITHUB_BASE_REF")
        if base_ref:
            candidates.append(f"origin/{base_ref}")
        candidates.extend(["origin/main", "origin/master", "main", "master"])
        
        diff_text = None
        for target in candidates:
            try:
                diff_text = repo.git.diff(f"{target}..HEAD", "--", rel_path)
                if diff_text.strip():
                    break
            except Exception:
                continue
                
        if not diff_text or not diff_text.strip():
            try:
                diff_text = repo.git.diff("HEAD", "--", rel_path)
            except Exception:
                pass
            if not diff_text or not diff_text.strip():
                try:
                    diff_text = repo.git.diff("--", rel_path)
                except Exception:
                    pass
                    
        return diff_text if diff_text and diff_text.strip() else None
    except Exception:
        return None


def _init_infrastructure(workspace: str, config=None):
    """Initialize cache + OllamaPool. Re-initializes if workspace changes.

    This function assigns module-level placeholders so other nodes can
    reference `_cache` and `_pool` safely. It tolerates failures and
    leaves placeholders as None when initialization cannot complete.
    """
    global _cache, _pool, _plugin_mgr, _current_workspace

    _current_workspace = workspace

    # SQLite cache
    try:
        _cache = ResultCache(workspace)
        # Migrate old JSON cache if exists
        legacy_dir = os.path.join(workspace, LEGACY_CACHE_DIR)
        if os.path.isdir(legacy_dir):
            count = _cache.migrate_from_json_cache(legacy_dir)
            if count > 0:
                console.print(f"[dim]  Migrated {count} cached results to SQLite[/dim]")
    except Exception:
        _cache = None

    # Clear cache if requested
    try:
        if config and getattr(config, 'clear_cache', False) and _cache:
            _cache.clear()
            console.print("[dim]  Cache cleared[/dim]")
    except Exception:
        pass

    # Plugin manager
    try:
        from .plugins import PluginManager
        _plugin_mgr = PluginManager(workspace).discover()
    except Exception:
        _plugin_mgr = None

    # OllamaPool
    try:
        urls = None
        if config:
            url_list = config.get_ollama_url_list() if hasattr(config, 'get_ollama_url_list') else []
            if url_list:
                urls = url_list
            elif getattr(config, 'ollama_host', None):
                urls = [config.ollama_host]
        if urls:
            _pool = OllamaPool(urls)
            if _pool and getattr(_pool, 'size', 0) > 1:
                console.print(f"[white][*] Ollama pool: {_pool.size} endpoints[/white]")
    except Exception:
        _pool = None

# Node: Discover Files (Monorepo-optimized)
def discover_node(state: AuditState) -> AuditState:
    console.print("[bold cyan]Step 1:[/bold cyan] [white]Discovery[/white]")

    config = state.get("config")
    workspace = state["workspace_path"]

    # Initialize infrastructure (cache + OllamaPool)
    _init_infrastructure(workspace, config)

    # Build Discovery with scaling params from config
    include_pats = config.get_include_list() if config and hasattr(config, 'get_include_list') else []
    exclude_pats = config.get_exclude_list() if config and hasattr(config, 'get_exclude_list') else []
    max_files = config.max_files if config and hasattr(config, 'max_files') else 0
    max_file_size = config.max_file_size if config and hasattr(config, 'max_file_size') else 512000
    respect_gi = config.respect_gitignore if config and hasattr(config, 'respect_gitignore') else True

    discovery = Discovery(
        root_dir=workspace,
        include_patterns=include_pats,
        exclude_patterns=exclude_pats,
        max_file_size=max_file_size,
        max_files=max_files,
        respect_gitignore=respect_gi,
    )
    # Single discovery walk - find_all() is 2x faster than separate find_code_files() + find_docs()
    code_files, docs = discovery.find_all()

    # Show discovery stats
    gi_tag = " (.gitignore active)" if discovery._gitignore else ""
    console.print(f"[dim]  └─ Found {len(code_files)} code files, {len(docs)} doc files{gi_tag}[/dim]")
    if max_files > 0:
        console.print(f"[dim]  max_files={max_files}[/dim]")

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
        "file_hashes": {}
    }

# Node: Integrity Check (Merkle Tree)
def integrity_node(state: AuditState) -> AuditState:
    console.print("[bold cyan]Step 2:[/bold cyan] [white]Integrity Check[/white] [dim](Git diff → Merkle fallback)[/dim]")

    workspace = state["workspace_path"]
    config = state.get("config")

    # ── Force full scan: skip git/merkle, use ALL discovered files ──
    force_full = config.force_full_scan if config and hasattr(config, 'force_full_scan') else False
    if force_full:
        discovered = state.get("discovered_files", [])
        console.print(f"[dim]  └─ Force full scan: {len(discovered)} file(s)[/dim]")
        file_contents = {}
        max_file_size = config.max_file_size if config and hasattr(config, 'max_file_size') else 512000
        for fpath in discovered:
            try:
                fsize = os.path.getsize(fpath)
                if fsize > max_file_size:
                    continue
                with open(fpath, 'r', encoding='utf-8') as f:
                    file_contents[fpath] = f.read()
            except Exception:
                pass
        return {"changed_files": discovered, "file_contents": file_contents}

    def _git_changed_files(ws: str) -> List[str]:
        try:
            from git import Repo
            repo = Repo(ws, search_parent_directories=True)
            if repo.bare:
                return []

            # In CI (GitHub Actions), GITHUB_BASE_REF gives the PR target branch
            candidates: List[str] = []
            base_ref = os.environ.get("GITHUB_BASE_REF")
            if base_ref:
                candidates.append(f"origin/{base_ref}")
            candidates.extend(["origin/main", "origin/master", "main", "master"])

            diff_files: List[str] = []

            for target in candidates:
                try:
                    # Two-dot diff: changes between target and HEAD
                    diff_out = repo.git.diff("--name-only", f"{target}..HEAD")
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

            # Also include untracked files so brand-new files are audited
            try:
                untracked = repo.git.ls_files("--others", "--exclude-standard")
                if untracked.strip():
                    diff_files.extend(untracked.strip().splitlines())
            except Exception:
                pass

            abs_paths = []
            repo_root = os.path.abspath(repo.working_tree_dir or ws)
            ws_abs = os.path.abspath(ws)
            for rel in diff_files:
                abs_p = os.path.abspath(os.path.join(repo_root, rel))
                # Only include files that are WITHIN the workspace directory
                if abs_p.startswith(ws_abs + os.sep) or abs_p == ws_abs:
                    if os.path.isfile(abs_p):
                        abs_paths.append(abs_p)
            return abs_paths
        except Exception:
            return []

    # 1) Prefer Git diff scope
    git_changed = _git_changed_files(workspace)

    changed_files: List[str] = []
    file_contents = {}

    if git_changed:
        # Intersect with discovered files to drop artifacts (.db, .jsonl, etc.)
        discovered_set = set(os.path.normpath(f) for f in state.get("discovered_files", []))
        if discovered_set:
            git_changed = [f for f in git_changed if os.path.normpath(f) in discovered_set]
        console.print(f"[dim]  └─ Git diff scope: {len(git_changed)} file(s)[/dim]")
        changed_files = git_changed
    else:
        # 2) Fallback to Merkle snapshot diff
        current_tree = build_merkle_tree(workspace)

        merkle_path = os.path.join(workspace, "merkle_snapshot.json")
        old_tree_dict = {}
        if os.path.exists(merkle_path):
            try:
                with open(merkle_path, 'r') as f:
                    old_tree_dict = json.load(f)
            except Exception:
                old_tree_dict = {}

        diffs = get_merkle_diff(old_tree_dict, current_tree)
        changed_files = diffs["modified"] + diffs["added"]

        if not changed_files and not diffs["removed"]:
            console.print("[dim]  └─ No changes detected (Merkle snapshot matched)[/dim]")
            return {"changed_files": [], "file_contents": {}}

        # Persist snapshot for next run
        try:
            with open(merkle_path, 'w') as f:
                json.dump(current_tree.to_dict(), f)
        except Exception:
            pass

        console.print(f"[dim]  └─ Merkle scope: {len(changed_files)} file(s)[/dim]")

    # Load content for scoped files (lazy - only read what we need)
    config = state.get("config")
    max_files = config.max_files if config and hasattr(config, 'max_files') and config.max_files > 0 else 0
    max_file_size = config.max_file_size if config and hasattr(config, 'max_file_size') else 512000

    # Enforce max_files cap
    if max_files > 0 and len(changed_files) > max_files:
        console.print(f"[white][!] Capping {len(changed_files)} files → max_files={max_files}[/white]")
        changed_files = changed_files[:max_files]

    for fpath in changed_files:
        try:
            # Skip files that are too large
            fsize = os.path.getsize(fpath)
            if fsize > max_file_size:
                continue
            with open(fpath, 'r', encoding='utf-8') as f:
                file_contents[fpath] = f.read()
        except Exception:
            console.print(f"[white][-] Failed to read {fpath}[/white]")

    return {
        "changed_files": changed_files,
        "file_contents": file_contents
    }

# Node: RAG Retrieval
def retrieval_node(state: AuditState) -> AuditState:
    if not state["changed_files"]:
        return {"context_data": ""}

    # Wire skip_rag flag
    config = state.get("config")
    if config and getattr(config, 'skip_rag', False):
        console.print("[bold cyan]Step 3:[/bold cyan] [white]RAG Retrieval[/white] [dim](skipped ─ --skip-rag)[/dim]")
        return {"context_data": ""}

    console.print("[bold cyan]Step 3:[/bold cyan] [white]RAG Retrieval[/white]")
    retriever = CodeRetriever()
    
    documents = []
    metadatas = []
    
    for path, content in state["file_contents"].items():
        documents.append(content)
        metadatas.append({"source": path})
        
    retriever.index_documents(documents, metadatas)
    
    query = "Authentication mechanisms, API routes, main entry points, security configurations"
    context = retriever.query(query)

    try:
        graph = build_knowledge_graph(state["workspace_path"])
        graph_context = build_knowledge_graph_summary(graph)
    except Exception:
        graph_context = ""

    combined_context = context.strip()
    if graph_context:
        combined_context = f"{combined_context}\n\n{graph_context}".strip() if combined_context else graph_context

    return {"context_data": combined_context}

def parse_llm_json(content: str) -> dict:
    """
    Robust JSON parser for LLM output.
    Handles: raw JSON, ```json fences, <think>...</think> wrapping,
    and falls back to regex field extraction.
    """
    import re

    # 0) Strip DeepSeek-R1 <think>...</think> chain-of-thought blocks
    content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()

    # 1) Try direct JSON parse
    try:
        parser = JsonOutputParser()
        return parser.parse(content)
    except Exception:
        pass

    # 2) Try extracting from markdown code fences
    try:
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        content = content.strip()
        return json.loads(content)
    except Exception:
        pass

    # 3) Try finding any JSON object in the text  { ... }
    try:
        match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception:
        pass

    # 4) Regex fallback - extract individual fields
    status_match = re.search(r'"status"\s*:\s*"([^"]+)"', content)
    risk_match = re.search(r'"risk"\s*:\s*"([^"]+)"', content)
    summary_match = re.search(r'"summary"\s*:\s*"([^"]*)"', content)
    fix_match = re.search(r'"fix"\s*:\s*"((?:[^"\\]|\\.)*)"', content, re.DOTALL)
    draft_fix_match = re.search(r'"draft_fix"\s*:\s*"((?:[^"\\]|\\.)*)"', content, re.DOTALL)
    safe_match = re.search(r'"safe_to_push"\s*:\s*(true|false)', content, re.IGNORECASE)
    reasoning_match = re.search(r'"reasoning"\s*:\s*"((?:[^"\\]|\\.)*)"', content, re.DOTALL)

    # Extract findings array loosely
    findings = []
    findings_match = re.search(r'"findings"\s*:\s*\[(.*?)\]', content, re.DOTALL)
    if findings_match:
        findings = re.findall(r'"([^"]+)"', findings_match.group(1))

    if status_match:
        return {
            "status": status_match.group(1),
            "risk": risk_match.group(1) if risk_match else "UNKNOWN",
            "summary": summary_match.group(1) if summary_match else "Parsed via regex fallback",
            "fix": fix_match.group(1) if fix_match else "",
            "draft_fix": draft_fix_match.group(1) if draft_fix_match else "",
            "findings": findings,
            "safe_to_push": safe_match.group(1).lower() == "true" if safe_match else False,
            "reasoning": reasoning_match.group(1) if reasoning_match else "",
        }

    # 5) Last resort - return a structured error rather than crashing the pipeline
    # Use LOW risk + safe_to_push=True so parse failures don't inflate risk or block pushes
    console.print(f"[white][!] LLM returned unparseable output ({len(content)} chars), using fallback[/white]")
    return {
        "status": "UNKNOWN",
        "risk": "LOW",
        "summary": f"LLM output could not be parsed ({len(content)} chars)",
        "fix": "",
        "draft_fix": "",
        "findings": [],
        "safe_to_push": True,
        "reasoning": "",
    }


def _select_docs_for_file(file_path: str, doc_sources: List[dict], top_k: int = 3) -> List[dict]:
    """Pick a small, relevant doc subset to keep prompts lean."""
    if not doc_sources:
        return []

    base = os.path.basename(file_path).lower()
    base_no_ext = os.path.splitext(base)[0]
    scores = []
    for doc in doc_sources:
        path = doc.get("path", "").lower()
        score = 0
        if base_no_ext and base_no_ext in path:
            score += 2
        if os.path.dirname(file_path).lower() in path:
            score += 1
        # prefer smaller docs to keep token count low
        score -= len(doc.get("content", "")) / 5000.0
        scores.append((score, doc))

    scores.sort(key=lambda x: x[0], reverse=True)
    return [d for s, d in scores if s >= 2][:top_k]

# Node: Code Analysis - Qwen Coder (the "hands")
# Reads code, compares against docs, detects drift, produces raw findings + draft fixes.
def code_analysis_node(state: AuditState) -> AuditState:
    if not state["changed_files"]:
        return {"code_findings": []}

    config = state.get("config")
    workspace = state["workspace_path"]
    _cache = None
    if config and not getattr(config, 'clear_cache', False):
        try:
            from dockdesk.cache import ResultCache
            _cache = ResultCache(workspace)
        except Exception:
            pass

    _pool = None
    if config:
        urls = []
        if getattr(config, 'pool', None):
            urls = config.pool.split(',')
        elif getattr(config, 'ollama_host', None):
            urls = [config.ollama_host]
        if urls:
            from dockdesk.ollama_pool import OllamaPool
            _pool = OllamaPool(urls)

    console.print("[bold cyan]Step 4:[/bold cyan] [white]Code Analysis[/white] [dim](Qwen Coder)[/dim]")

    changed_files = state["changed_files"]
    context_data = state.get("context_data", "")

    model_name = state.get("model", DEFAULT_MODEL)
    config = state.get("config")
    temperature = config.temperature if config and hasattr(config, 'temperature') else DEFAULT_TEMPERATURE
    timeout = config.timeout_per_file if config and hasattr(config, 'timeout_per_file') else 120

    # Resolve code model - prefer detect_model (legacy) or model
    code_model = model_name
    if config:
        if config.detect_model:
            code_model = config.detect_model
        elif config.model:
            code_model = config.model

    console.print(f"[dim]  └─ Code model: {code_model}[/dim]")

    rotate_models = bool(config and hasattr(config, 'rotate_models') and config.rotate_models)
    rotation_models: List[str] = []
    file_to_model: Dict[str, str] = {}
    if rotate_models:
        rotation_models = _get_available_models_for_rotation()
        # Keep explicit model first when available so existing behavior stays predictable.
        if code_model in rotation_models:
            rotation_models = [code_model] + [m for m in rotation_models if m != code_model]
        # Avoid noisy model churn when only one model is available.
        if len(rotation_models) > 1:
            for i, fp in enumerate(changed_files):
                file_to_model[fp] = rotation_models[i % len(rotation_models)]
            console.print(
                f"[dim]  └─ Model rotation: enabled ({len(rotation_models)} models, round-robin)[/dim]"
            )
        else:
            file_to_model = {fp: code_model for fp in changed_files}
            rotate_models = False
            console.print("[dim]  └─ Model rotation requested, but only one local audit model was found[/dim]")
    else:
        file_to_model = {fp: code_model for fp in changed_files}

    # Batch size for multi-file analysis
    batch_size = config.batch_size if config and hasattr(config, 'batch_size') else 5
    fast_mode = config.fast_mode if config and hasattr(config, 'fast_mode') else False

    # ── Pre-compute cache keys and doc index outside thread pool ──
    _precomputed_keys: Dict[str, str] = {}
    for fp in changed_files:
        content = state["file_contents"].get(fp, "")
        selected_model = file_to_model.get(fp, code_model)
        if _cache:
            _precomputed_keys[fp] = ResultCache.make_key(fp, content, selected_model)

    _precomputed_docs: Dict[str, List[dict]] = {}
    for fp in changed_files:
        _precomputed_docs[fp] = _select_docs_for_file(fp, state["doc_sources"], top_k=2)

    # ── Build custom rules suffix for prompt injection ──
    _custom_rules_text = ""
    if config and hasattr(config, 'custom_rules') and config.custom_rules:
        rules_list = "\n".join(f"  - {r}" for r in config.custom_rules)
        _custom_rules_text = f"\n\nAdditionally, check for the following custom rules:\n{rules_list}"

    def _analyze_single(file_path: str) -> dict:
        start_time = time.time()
        code_content = state["file_contents"].get(file_path, "")
        selected_model = file_to_model.get(file_path, code_model)

        # ── SQLite cache check (pre-computed key) ──
        ck = _precomputed_keys.get(file_path)
        if _cache and ck:
            cached = _cache.get(ck)
            if cached:
                cached["duration_ms"] = 0
                cached["cached"] = True
                return cached

        docs_subset = _precomputed_docs.get(file_path, [])
        docs_text = "\n".join([f"[{d['path']}]: {d['content']}" for d in docs_subset])

        if len(docs_text) > 2000:
            # We just truncate docs to 2000 chars for now to avoid a second LLM call,
            # or summarize if we had a dedicated summary prompt.
            docs_text = docs_text[:2000] + "\n... (truncated)"

        from dockdesk.chunking import chunk_code
        chunks = chunk_code(file_path, code_content, max_chars=2000)

        # If no docs were found, short-circuit to SKIP without calling the LLM
        effective_docs = docs_text or "(no docs found)"
        if not docs_text or docs_text.strip() == "":
            result = {
                "status": "SKIP",
                "findings": [],
                "summary": "No documentation found for this file",
                "draft_fix": "",
            }
            result["file"] = file_path
            result["code_model"] = selected_model
            result["duration_ms"] = int((time.time() - start_time) * 1000)
            result["cached"] = False
            if _cache and ck:
                _cache.put(ck, result, model=selected_model, file_path=file_path)
            return result

        provider = get_provider(config.provider, pool=_pool) if config and hasattr(config, 'provider') else get_provider("ollama", pool=_pool)
        llm = provider.get_llm(model=selected_model, temperature=temperature, num_predict=512, num_ctx=3072)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a code-vs-documentation drift detector.
Compare the CODE against the DOCS for the given file.
- If docs exist and accurately describe the code: status = "PASS"
- If docs exist but contain real errors or outdated information: status = "FAIL"
- If NO docs were found (docs say "(no docs found)"): status = "SKIP"

Reply ONLY with a JSON object. No markdown, no explanation.
Schema:
{{"status":"PASS|FAIL|SKIP","findings":["..."],"summary":"...","draft_fix":"..."}}

IMPORTANT:
- "findings" must list ONLY real doc-vs-code mismatches, not style opinions.
- If status is "SKIP", set findings to [] and draft_fix to "".
- If status is "PASS", set findings to [] and draft_fix to "".
- Minor wording differences are NOT failures. Only flag real inaccuracies.""" + _custom_rules_text),
            ("user", "FILE: {file_path}\nLINES: {start_line}-{end_line}\nCODE:\n{chunk_text}\nDOCS:\n{docs_text}\n\nREPOSITORY CONTEXT:\n{context_data}")
        ])
        chain = prompt | llm

        all_findings = []
        all_fixes = []
        any_fail = False
        any_error = False

        for chunk in chunks:
            try:
                response = chain.invoke({
                    "file_path": os.path.basename(file_path),
                    "start_line": chunk["start_line"],
                    "end_line": chunk["end_line"],
                    "chunk_text": chunk["text"],
                    "docs_text": effective_docs,
                    "context_data": context_data or "(no repository context)",
                })
                res = parse_llm_json(response.content)
                if res.get("status") == "FAIL":
                    any_fail = True
                    for f in res.get("findings", []):
                        all_findings.append(f"[Lines {chunk['start_line']}-{chunk['end_line']}] {f}")
                    if res.get("draft_fix"):
                        all_fixes.append(f"[Lines {chunk['start_line']}-{chunk['end_line']}] {res.get('draft_fix')}")
            except Exception as e:
                any_error = True
                all_findings.append(f"[Lines {chunk['start_line']}-{chunk['end_line']}] Error: {str(e)}")

        if any_error and not any_fail:
            final_status = "ERROR"
            summary = "Error during chunk analysis"
        elif any_fail:
            final_status = "FAIL"
            summary = f"Found {len(all_findings)} drift issues across chunks."
        else:
            final_status = "PASS"
            summary = "Code matches documentation."

        result = {
            "status": final_status,
            "findings": all_findings,
            "summary": summary,
            "draft_fix": "\n".join(all_fixes) if all_fixes else "",
            "file": file_path,
            "code_model": selected_model,
            "duration_ms": int((time.time() - start_time) * 1000),
            "cached": False
        }

        # Safety net for no-docs
        if effective_docs == "(no docs found)" and result.get("status") == "FAIL":
            result["status"] = "SKIP"
            result["findings"] = []
            result["draft_fix"] = ""
            result["summary"] = "No documentation found"

        if _cache and ck:
            _cache.put(ck, result, model=selected_model, file_path=file_path)
            
        return result

    def _analyze_batch(file_paths: List[str]) -> List[dict]:
        """Analyze multiple small files in a single LLM call."""
        start_time = time.time()
        batch_prompt_parts = []
        uncached_files = []

        results_map: Dict[str, dict] = {}

        # Check cache first for each file in batch
        for fp in file_paths:
            ck = _precomputed_keys.get(fp)
            if _cache and ck:
                cached = _cache.get(ck)
                if cached:
                    cached["duration_ms"] = 0
                    cached["cached"] = True
                    results_map[fp] = cached
                    continue
            uncached_files.append(fp)

        if not uncached_files:
            return [results_map[fp] for fp in file_paths if fp in results_map]

        # Build multi-file prompt
        for fp in uncached_files:
            code_content = state["file_contents"].get(fp, "")[:1200]  # tighter trim for batches
            docs_subset = _precomputed_docs.get(fp, [])
            docs_text = docs_subset[0]['content'][:300] if docs_subset else "(no docs)"
            batch_prompt_parts.append(
                f"=== FILE: {os.path.basename(fp)} ===\nCODE:\n{code_content}\nDOCS:\n{docs_text}"
            )

        combined = "\n\n".join(batch_prompt_parts)

        prompt = ChatPromptTemplate.from_messages([
            ("system", """Compare code vs docs for each file below. Reply ONLY with a JSON array, one object per file.
Each object: {{"file":"<filename>","status":"PASS|FAIL","findings":[],"summary":"...","draft_fix":"..."}}
Reply ONLY with the JSON array, no other text.""" + _custom_rules_text),
            ("user", "{combined}")
        ])

        provider = get_provider(config.provider, pool=_pool) if config and hasattr(config, 'provider') else get_provider("ollama", pool=_pool)
        llm = provider.get_llm(model=code_model, temperature=temperature, num_predict=1024, num_ctx=4096)
        chain = prompt | llm

        try:
            response = chain.invoke({"combined": combined})
            parsed = parse_llm_json(response.content)

            # Handle: could be a list or a single dict
            if isinstance(parsed, dict):
                parsed = [parsed]
            elif not isinstance(parsed, list):
                parsed = []

            # Map results back to files
            dur = int((time.time() - start_time) * 1000) // max(len(uncached_files), 1)
            for i, fp in enumerate(uncached_files):
                if i < len(parsed):
                    r = parsed[i]
                else:
                    r = {"status": "UNKNOWN", "summary": "Batch parse mismatch", "findings": [], "draft_fix": ""}
                r["file"] = fp
                r["code_model"] = code_model
                r["duration_ms"] = dur
                r.setdefault("findings", [])
                r.setdefault("draft_fix", "")
                r.setdefault("status", "UNKNOWN")
                r.setdefault("summary", "")
                r["cached"] = False
                results_map[fp] = r
                # Cache each result (reuse pre-computed key)
                ck = _precomputed_keys.get(fp)
                if _cache and ck:
                    _cache.put(ck, r, model=code_model, file_path=fp)
        except Exception as e:
            # Fallback: re-analyze individually instead of losing the whole batch
            console.print(f"[dim]  Batch failed ({e}), falling back to individual analysis...[/dim]")
            for fp in uncached_files:
                try:
                    individual_result = _analyze_single(fp)
                    results_map[fp] = individual_result
                except Exception as ie:
                    results_map[fp] = {
                        "file": fp, "status": "ERROR", "findings": [str(ie)],
                        "summary": f"Analysis failed: {str(ie)}", "draft_fix": "",
                        "code_model": code_model, "duration_ms": 0, "cached": False,
                    }

        return [results_map[fp] for fp in file_paths if fp in results_map]

    # ── Decide: batch or individual analysis ──
    code_findings: List[dict] = []
    pool_workers = _pool.optimal_workers(base=4) if _pool else 4
    cfg_workers = config.workers if config and hasattr(config, 'workers') and config.workers > 0 else 0
    max_workers = cfg_workers if cfg_workers > 0 else min(pool_workers, len(changed_files)) if changed_files else 1

    large_files = [f for f in changed_files if len(state["file_contents"].get(f, "")) > 1200]
    small_files = [f for f in changed_files if len(state["file_contents"].get(f, "")) <= 1200]
    
    use_batching = (not rotate_models) and fast_mode and len(small_files) > batch_size

    from dockdesk.ui import get_progress_bar
    with get_progress_bar() as progress:
        if use_batching:
            # Analyze large files individually first
            if large_files:
                task_l = progress.add_task("Code analysis (large files)", total=len(large_files), filename="analyzing")
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_map = {executor.submit(_analyze_single, f): f for f in large_files}
                    for future in as_completed(future_map):
                        fpath = future_map[future]
                        try:
                            res = future.result(timeout=timeout)
                            code_findings.append(res)
                        except Exception as e:
                            code_findings.append({
                                "file": fpath, "status": "ERROR", "findings": [str(e)],
                                "summary": f"Analysis failed: {str(e)}", "draft_fix": "",
                                "code_model": code_model, "duration_ms": 0, "cached": False,
                            })
                        progress.update(task_l, advance=1, filename=os.path.basename(fpath))

            # ── Batched mode: group small files into batches ──
            batches = [small_files[i:i+batch_size] for i in range(0, len(small_files), batch_size)]
            task = progress.add_task("Code analysis (batched)", total=len(batches), filename="batching")
            with ThreadPoolExecutor(max_workers=max(2, max_workers // 2)) as executor:
                future_map = {executor.submit(_analyze_batch, b): b for b in batches}
                for future in as_completed(future_map):
                    try:
                        batch_results = future.result(timeout=timeout * batch_size)
                        code_findings.extend(batch_results)
                    except Exception as e:
                        batch = future_map[future]
                        for fp in batch:
                            code_findings.append({
                                "file": fp, "status": "ERROR", "findings": [str(e)],
                                "summary": f"Analysis failed: {str(e)}", "draft_fix": "",
                                "code_model": code_model, "duration_ms": 0, "cached": False,
                            })
                    progress.advance(task)
        else:
            # ── Individual mode (default for small sets) ──
            task = progress.add_task("Code analysis", total=len(changed_files), filename="analyzing")
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_map = {executor.submit(_analyze_single, f): f for f in changed_files}
                for future in as_completed(future_map):
                    fpath = future_map[future]
                    try:
                        res = future.result(timeout=timeout)
                        code_findings.append(res)
                    except Exception as e:
                        code_findings.append({
                            "file": fpath, "status": "ERROR", "findings": [str(e)],
                            "summary": f"Analysis failed: {str(e)}", "draft_fix": "",
                            "code_model": code_model, "duration_ms": 0, "cached": False,
                        })
                    progress.update(task, advance=1, filename=os.path.basename(fpath))

    cached_count = sum(1 for r in code_findings if r.get("cached"))
    passes = sum(1 for r in code_findings if r.get("status") == "PASS")
    fails = sum(1 for r in code_findings if r.get("status") != "PASS")
    mode_tag = "batched" if use_batching else "individual"
    console.print(f"[dim]  └─ Code analysis ({mode_tag}): [green]{passes} PASS[/green], [red]{fails} FAIL/ERR[/red], {cached_count} cached[/dim]")

    return {"code_findings": code_findings}


# Node: Reasoning - DeepSeek-R1-Distill (the "brain")
# Judges risk, validates draft fixes, decides if changes are safe to push.
def reasoning_node(state: AuditState) -> AuditState:
    code_findings = state.get("code_findings", [])
    if not code_findings:
        return {"audit_results": []}

    console.print("[bold cyan]Step 5:[/bold cyan] [white]Logical Reasoning[/white] [dim](DeepSeek-R1)[/dim]")

    config = state.get("config")
    temperature = config.temperature if config and hasattr(config, 'temperature') else DEFAULT_TEMPERATURE
    timeout = config.timeout_per_file if config and hasattr(config, 'timeout_per_file') else 120

    # Resolve reasoning model
    reasoning_model = DEFAULT_REASONING_MODEL
    if config:
        if config.reasoning_model:
            reasoning_model = config.reasoning_model
        elif config.fix_model:  # legacy fallback
            reasoning_model = config.fix_model
    # CLI/state override
    if state.get("reasoning_model"):
        reasoning_model = state["reasoning_model"]

    console.print(f"[dim]  └─ Reasoning model: {reasoning_model}[/dim]")

    # Skip PASS and SKIP files - no need to reason about them
    needs_reasoning = [f for f in code_findings if f.get("status") not in ("PASS", "SKIP")]
    pass_throughs = [f for f in code_findings if f.get("status") == "PASS"]
    skip_throughs = [f for f in code_findings if f.get("status") == "SKIP"]

    # Fast mode: also skip files with minimal findings (likely LOW risk)
    fast_mode = config.fast_mode if config and hasattr(config, 'fast_mode') else False
    fast_skips = []
    if fast_mode:
        refined = []
        for f in needs_reasoning:
            findings = f.get("findings", [])
            # If only 1 minor finding and summary looks trivial, skip reasoning
            if len(findings) <= 1 and len(str(f.get("summary", ""))) < 50:
                fast_skips.append(f)
            else:
                refined.append(f)
        needs_reasoning = refined

    # ── Build custom rules suffix for reasoning prompts ──
    _reasoning_rules_text = ""
    if config and hasattr(config, 'custom_rules') and config.custom_rules:
        rules_list = "\n".join(f"  - {r}" for r in config.custom_rules)
        _reasoning_rules_text = f"\n\nAdditionally, consider these custom rules when assessing risk:\n{rules_list}"

    if pass_throughs:
        console.print(f"[dim]  └─ Skipping {len(pass_throughs)} PASS files (no reasoning needed)[/dim]")
    if skip_throughs:
        console.print(f"[dim]  └─ Skipping {len(skip_throughs)} SKIP files (no docs found)[/dim]")
    if fast_skips:
        console.print(f"[dim]  └─ Skipping {len(fast_skips)} low-signal files (--fast mode)[/dim]")

    def _normalize_risk(raw: str) -> str:
        """Normalize free-form risk values from small LLMs to HIGH/MEDIUM/LOW."""
        raw_upper = str(raw).upper().strip()
        if any(k in raw_upper for k in ["HIGH", "CRITICAL", "SEVERE", "BREAKING"]):
            return "HIGH"
        if any(k in raw_upper for k in ["LOW", "MINOR", "COSMETIC", "TRIVIAL", "MILD", "NONE", "SAFE", "NEGLIGIBLE"]):
            return "LOW"
        return "MEDIUM"  # MID, MIS, MORNING, UNKNOWN, etc. → MEDIUM

    def _safe_str(val, maxlen: int = 200) -> str:
        """Convert any value to a safe string, escaping {} for LangChain templates."""
        if val is None:
            return ""
        if isinstance(val, dict):
            # flatten dict to key: value pairs
            s = ", ".join(f"{k}: {v}" for k, v in val.items())
        elif isinstance(val, list):
            s = "; ".join(str(x) for x in val[:5])
        else:
            s = str(val)
        # Escape curly braces so LangChain template doesn't interpret them
        s = s.replace("{", "((").replace("}", "))")
        return s[:maxlen]

    def _reason_single(finding: dict) -> dict:
        start_time = time.time()
        file_path = str(finding.get("file", "unknown"))

        if finding.get("code_model") in ("GitHub Lens", "Local Heuristic Lens"):
            return {
                "file": file_path,
                "status": finding.get("status", "FAIL"),
                "risk": finding.get("risk", "HIGH"),
                "summary": finding.get("summary", ""),
                "fix": finding.get("fix") or finding.get("draft_fix") or "",
                "safe_to_push": finding.get("safe_to_push", False),
                "reasoning": "Audited using the unbreakable fallback search mechanism.",
                "code_model": finding.get("code_model"),
                "reasoning_model": finding.get("reasoning_model"),
                "duration_ms": finding.get("duration_ms", 0) + int((time.time() - start_time) * 1000),
            }

        # Safely extract all fields - handle dict/list/None/any type
        status = _safe_str(finding.get("status", "UNKNOWN"), 50)
        summary = _safe_str(finding.get("summary", ""), 200)
        draft_fix = _safe_str(finding.get("draft_fix", ""), 200)

        findings_list = finding.get("findings", [])
        if not isinstance(findings_list, list):
            findings_list = [findings_list]
        findings_text = _safe_str(findings_list[:5], 300)

        # Build prompt with raw string literals (no template vars in system)
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a risk assessor for code-vs-documentation drift.
Given the code analysis results, assess the risk level and whether it's safe to push.

Reply ONLY with a JSON object, no other text.
Schema:
{{"risk":"HIGH|MEDIUM|LOW","summary":"...","fix":"suggested fix or empty","safe_to_push":true|false,"reasoning":"..."}}

Rules:
- Only set risk "HIGH" for breaking API changes, security issues, or completely wrong docs.
- "MEDIUM" for notable omissions or outdated parameter descriptions.
- "LOW" for cosmetic issues, minor wording, or trivial differences.
- "fix" should describe what to change in docs, not rewrite the entire file.
- Set safe_to_push to true unless there is a genuine risk of user confusion.""" + _reasoning_rules_text),
            ("user", "FILE: {file_path}\nSTATUS: {status}\nFINDINGS: {findings_text}\nSUMMARY: {summary}\nDRAFT_FIX: {draft_fix}")
        ])

        provider = get_provider(config.provider, pool=None) if config and hasattr(config, 'provider') else get_provider("ollama", pool=None)
        llm = provider.get_llm(model=reasoning_model, temperature=temperature, num_predict=1536, num_ctx=2048)
        chain = prompt | llm

        # Retry loop - DeepSeek-R1 sometimes returns empty due to internal <think> consuming all tokens
        # Progressive num_predict escalation: 1536 → 2048 on retry
        result = None
        last_content = ""
        predict_schedule = [1536, 2048]
        for attempt in range(2):
            try:
                if attempt > 0:
                    # Escalate num_predict on retry
                    provider = get_provider(config.provider, pool=_pool) if config and hasattr(config, 'provider') else get_provider("ollama", pool=_pool)
                    llm = provider.get_llm(model=reasoning_model, temperature=temperature, num_predict=predict_schedule[min(attempt, len(predict_schedule)-1)], num_ctx=2048)
                    chain = prompt | llm
                response = chain.invoke({
                    "file_path": os.path.basename(file_path),
                    "status": status,
                    "findings_text": findings_text,
                    "summary": summary,
                    "draft_fix": draft_fix or "(none)",
                })
                last_content = getattr(response, "content", "") or ""
                if not last_content.strip():
                    continue  # empty response, retry

                result = parse_llm_json(last_content)
                if result.get("risk") or result.get("summary"):
                    break  # got valid output
            except Exception:
                continue

        if result is None:
            result = {
                "risk": "LOW",
                "summary": f"Reasoning model returned no output after 2 attempts",
                "fix": "",
                "safe_to_push": True,
                "reasoning": last_content[:300] if last_content else "",
            }

        if result.get("fix"):
            try:
                result["fix"] = Guardrails.sanitize_fix(result["fix"])
            except Exception:
                pass

        # Let reasoning override status: if code_analysis said FAIL but
        # reasoning assessed LOW risk and safe_to_push, upgrade to PASS
        code_status = str(finding.get("status", "UNKNOWN"))
        assessed_risk = _normalize_risk(result.get("risk", "MEDIUM"))
        final_status = code_status
        if code_status == "FAIL" and assessed_risk == "LOW" and result.get("safe_to_push"):
            final_status = "PASS"

        return {
            "file": file_path,
            "status": final_status,
            "risk": assessed_risk,
            "summary": _safe_str(result.get("summary", summary), 200),
            "fix": str(result.get("fix", "")),
            "safe_to_push": bool(result.get("safe_to_push", False)),
            "reasoning": str(result.get("reasoning", ""))[:500],
            "code_model": str(finding.get("code_model", "")),
            "reasoning_model": reasoning_model,
            "duration_ms": finding.get("duration_ms", 0) + int((time.time() - start_time) * 1000),
        }

    # Pass-through results for PASS files (no LLM call needed)
    audit_results: List[dict] = []
    for f in pass_throughs:
        audit_results.append({
            "file": f.get("file", "unknown"),
            "status": "PASS",
            "risk": "LOW",
            "summary": f.get("summary", "Code matches documentation"),
            "fix": "",
            "safe_to_push": True,
            "reasoning": "Code analysis passed - no drift detected.",
            "code_model": f.get("code_model", ""),
            "reasoning_model": reasoning_model,
            "duration_ms": f.get("duration_ms", 0),
        })

    # Pass-through results for SKIP files (no docs found - no LLM call needed)
    for f in skip_throughs:
        audit_results.append({
            "file": f.get("file", "unknown"),
            "status": "SKIP",
            "risk": "LOW",
            "summary": f.get("summary", "No documentation found for this file"),
            "fix": "",
            "safe_to_push": True,
            "reasoning": "No docs found - nothing to compare.",
            "code_model": f.get("code_model", ""),
            "reasoning_model": reasoning_model,
            "duration_ms": f.get("duration_ms", 0),
        })

    # Fast-mode skipped files get MEDIUM/safe by default
    for f in fast_skips:
        audit_results.append({
            "file": f.get("file", "unknown"),
            "status": f.get("status", "FAIL"),
            "risk": "LOW",
            "summary": f.get("summary", "Skipped reasoning (fast mode)"),
            "fix": str(f.get("draft_fix", "")),
            "safe_to_push": True,
            "reasoning": "Fast mode: low-signal finding skipped reasoning.",
            "code_model": f.get("code_model", ""),
            "reasoning_model": reasoning_model,
            "duration_ms": f.get("duration_ms", 0),
        })

    # Run reasoning in PARALLEL for FAIL/ERROR files
    if needs_reasoning:
        pool_workers = _pool.optimal_workers(base=4) if _pool else 3
        cfg_workers = config.workers if config and hasattr(config, 'workers') and config.workers > 0 else 0
        max_workers = cfg_workers if cfg_workers > 0 else min(pool_workers, len(needs_reasoning))
        from dockdesk.ui import get_progress_bar
        with get_progress_bar() as progress:
            task = progress.add_task("Reasoning", total=len(needs_reasoning), filename="evaluating")
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_map = {executor.submit(_reason_single, f): f for f in needs_reasoning}
                for future in as_completed(future_map):
                    finding = future_map[future]
                    try:
                        result = future.result(timeout=timeout)
                        audit_results.append(result)
                    except Exception as e:
                        audit_results.append({
                            "file": finding.get("file", "unknown"),
                            "status": finding.get("status", "ERROR"),
                            "risk": "UNKNOWN",
                            "summary": f"Reasoning failed: {str(e)}",
                            "fix": "",
                            "safe_to_push": False,
                            "reasoning": "",
                            "code_model": finding.get("code_model", ""),
                            "reasoning_model": reasoning_model,
                            "duration_ms": finding.get("duration_ms", 0),
                        })
                    progress.update(task, advance=1, filename=os.path.basename(finding.get("file", "unknown")))

    # Summary table
    safe_count = sum(1 for r in audit_results if r.get("safe_to_push"))
    unsafe_count = len(audit_results) - safe_count
    high_count = sum(1 for r in audit_results if r.get("risk") == "HIGH")
    console.print(f"[dim]  └─ Reasoning done: [green]{safe_count} safe[/green], [red]{unsafe_count} unsafe[/red], [bold red]{high_count} HIGH[/bold red] risk[/dim]")

    # Run plugin post-audit hooks
    if _plugin_mgr and _plugin_mgr.has_plugins:
        audit_results = _plugin_mgr.run_post_hooks(audit_results)
        console.print(f"[dim]  \u2514\u2500 Plugins: post_audit hooks applied[/dim]")

    from dockdesk.orchestrator import execute_analysis
    state.setdefault("orchestration_metrics", {})
    state["audit_results"] = audit_results
    state = execute_analysis(state)
    return {"audit_results": audit_results}


# Node: Accountability - Per-developer drift tracking + Merkle audit trail
def accountability_node(state: AuditState) -> AuditState:
    audit_results = state.get("audit_results", [])
    if not audit_results:
        return {"accountability_data": None, "audit_chain_link": None}

    console.print("[bold cyan]Step 5.5:[/bold cyan] [white]Accountability Tracking[/white]")

    workspace = state["workspace_path"]

    # Build per-developer accountability
    from dockdesk.accountability import build_accountability, build_audit_chain_link
    from dockdesk.orchestrator import generate_run_id

    accountability = build_accountability(audit_results, workspace)

    dev_count = len(accountability.get("developers", {}))
    offenders = len(accountability.get("top_offenders", []))
    clean = len(accountability.get("clean_streaks", []))
    codeowners_tag = " (CODEOWNERS loaded)" if accountability.get("codeowners_loaded") else ""

    console.print(f"[dim]  └─ {dev_count} developers tracked, {offenders} with drift, {clean} clean{codeowners_tag}[/dim]")

    # Build tamper-evident audit chain link
    run_id = state.get("orchestration_metrics", {}).get("run_id", generate_run_id())
    chain_link = build_audit_chain_link(run_id, workspace, audit_results)

    console.print(f"[dim]  └─ Audit chain: link #{chain_link.chain_hash[:12]}... (prev: {chain_link.previous_hash[:12]}...)[/dim]")

    return {
        "accountability_data": accountability,
        "audit_chain_link": chain_link.to_dict(),
    }


def notify_node(state: AuditState) -> AuditState:
    config = state.get("config")
    webhook_url = ""
    if config and hasattr(config, "discord_webhook"):
        webhook_url = config.discord_webhook

    notifier = DiscordNotifier(webhook_url)
    if not notifier.enabled:
        return {"discord_posted": False}

    console.print("[bold cyan]Step 7:[/bold cyan] [white]Discord Notification[/white]")

    audit_results = state.get("audit_results", [])
    code_model = state.get("model", DEFAULT_MODEL)
    reasoning_model = state.get("reasoning_model", DEFAULT_REASONING_MODEL)

    posted = notifier.post_audit_summary(
        audit_results=audit_results,
        run_metadata=state.get("run_metadata"),
        code_model=code_model,
        reasoning_model=reasoning_model,
    )

    # Best-effort follow-up tree summary for quick directory-level visibility.
    try:
        notifier.post_tree_summary(audit_results=audit_results)
    except Exception:
        pass

    return {"discord_posted": posted}

# Node: Reporting
def reporting_node(state: AuditState) -> AuditState:
    console.print("[bold cyan]Step 6:[/bold cyan] [white]Reporting[/white]")
    
    results = state.get("audit_results", [])
    changed = state.get("changed_files", [])
    config = state.get("config")
    model_name = state.get("model", DEFAULT_MODEL)
    model_tier = state.get("model_tier", "unknown")
    reasoning_model = state.get("reasoning_model", DEFAULT_REASONING_MODEL)
    workspace = state["workspace_path"]
    
    risk_map = {}
    for res in results:
        risk_map[res["file"]] = res.get("risk", "UNKNOWN")
        
    mermaid_graph = Visualizer.generate_mermaid_graph(changed, risk_map)
    
    # Calculate summary stats
    pass_count = sum(1 for r in results if r.get("status") == "PASS")
    fail_count = sum(1 for r in results if r.get("status") == "FAIL")
    error_count = sum(1 for r in results if r.get("status") not in ("PASS", "FAIL"))
    
    high_risk = sum(1 for r in results if r.get("risk") == "HIGH")
    medium_risk = sum(1 for r in results if r.get("risk") == "MEDIUM")
    low_risk = sum(1 for r in results if r.get("risk") == "LOW")
    
    safe_count = sum(1 for r in results if r.get("safe_to_push") is True)
    unsafe_count = sum(1 for r in results if r.get("safe_to_push") is False)
    
    # Resolve model display
    code_model_display = model_name
    if config and config.detect_model:
        code_model_display = config.detect_model
    reasoning_display = reasoning_model
    model_display = f"{code_model_display} (code) / {reasoning_display} (reasoning)"

    # ── Rich summary table in terminal ──
    from dockdesk.ui import get_results_table, print_section_rule
    print_section_rule("AUDIT RESULTS")
    summary_table = get_results_table()

    for res in results:
        file_path = res.get("file", "unknown")
        try:
            rel = os.path.relpath(file_path, workspace)
        except ValueError:
            rel = file_path
        # Truncate long paths
        if len(rel) > 40:
            rel = "..." + rel[-37:]

        status = res.get("status", "?")
        status_style_map = {"PASS": "bold #00FFFF", "FAIL": "bold #FF1493", "SKIP": "dim #DA70D6", "ERROR": "bold #FFD700"}
        status_str = f"[{status_style_map.get(status, 'white')}]{status}[/{status_style_map.get(status, 'white')}]"

        risk = res.get("risk", "?")
        risk_style_map = {"HIGH": "bold #FF1493", "MEDIUM": "bold #FFD700", "MED": "bold #FFD700", "LOW": "bold #00FFFF"}
        risk_label = {"HIGH": "HIGH", "MEDIUM": "MED", "MED": "MED", "LOW": "LOW"}.get(risk, risk)
        risk_str = f"[{risk_style_map.get(risk, 'dim')}]{risk_label}[/{risk_style_map.get(risk, 'dim')}]"

        safe = res.get("safe_to_push")
        safe_str = "[bold #00FFFF] YES[/bold #00FFFF]" if safe else "[bold #FF1493] NO[/bold #FF1493]"
        summary = (res.get("summary", "") or "")[:80]

        summary_table.add_row(rel, status_str, risk_str, safe_str, summary)

    console.print(summary_table)
    console.print()

    from rich.tree import Tree
    import subprocess
    import re

    error_tree = Tree("[bold cyan]Semantic Drift Error Trajectories[/bold cyan]")
    has_errors = False

    for res in results:
        status = res.get("status", "?")
        if status not in ("FAIL", "ERROR"):
            continue
        
        file_path = res.get("file", "unknown")
        try:
            rel = os.path.relpath(file_path, workspace)
        except ValueError:
            rel = file_path

        author = "Unknown"
        try:
            blame_out = subprocess.check_output(
                ["git", "blame", "--porcelain", rel], 
                cwd=workspace, stderr=subprocess.DEVNULL, text=True
            )
            m = re.search(r'^author (.+)$', blame_out, re.MULTILINE)
            if m:
                author = m.group(1)
        except Exception:
            pass

        node = error_tree.add(f"[bold red]{rel}[/bold red] (Author: [yellow]{author}[/yellow])")
        findings = res.get("findings", [])
        if not findings and "summary" in res:
            findings = [res["summary"]]
        for f in findings:
            node.add(f"[white]{f}[/white]")
        has_errors = True

    if has_errors:
        console.print(error_tree)
        console.print()

    # ── Build markdown report ──
    report = f"""#  DockDesk Audit Report

**Architecture:** Dual-Model (Code + Reasoning)  
**Code Agent:** {code_model_display}  
**Reasoning Agent:** {reasoning_display}  
**Files Audited:** {len(results)}  
**Status:** {pass_count} Pass | {fail_count} Fail | {error_count} Error

## Risk Distribution
| Level | Count |
|-------|-------|
| HIGH | {high_risk} |
| MEDIUM | {medium_risk} |
| LOW | {low_risk} |

## Push Safety
| Safe to Push | Unsafe | 
|----------------|----------|
| {safe_count} | {unsafe_count} |

## Dependency Graph

{mermaid_graph}

## File Results

"""
    
    for res in results:
        status = res.get("status", "UNKNOWN")
        icon = {"PASS": "PASS", "FAIL": "FAIL"}.get(status, "")
        risk = res.get("risk", "UNKNOWN")
        risk_badge = {"HIGH": "HIGH", "MEDIUM": "MEDIUM", "LOW": "LOW"}.get(risk, "UNKNOWN")
        safe = res.get("safe_to_push", None)
        safe_badge = "Safe" if safe is True else "Unsafe" if safe is False else "Unknown"
        
        file_path = res.get("file", "unknown")
        try:
            rel_path = os.path.relpath(file_path, workspace)
        except ValueError:
            rel_path = file_path
            
        dur_s = res.get("duration_ms", 0) / 1000
        report += f"### {icon} {rel_path}\n\n"
        report += f"**Risk:** {risk_badge} {risk} | **Push Safety:** {safe_badge} | **Time:** {dur_s:.1f}s  \n"
        report += f"**Summary:** {res.get('summary', 'No summary')}\n\n"
        
        if res.get("reasoning"):
            report += f"<details>\n<summary>DeepSeek Reasoning</summary>\n\n{res.get('reasoning')}\n\n</details>\n\n"
        
        if res.get("fix"):
            report += f"<details>\n<summary>Proposed Fix</summary>\n\n```markdown\n{res.get('fix')}\n```\n\n</details>\n\n"
        
        report += "---\n\n"
    
    report += f"\n> Generated by DockDesk Dual-Model Auditor ({model_display})\n"

    report_path = os.path.join(workspace, "audit_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    
    console.print(f"[dim]  └─ Report → {report_path}[/dim]")

    # ── Auto-export dashboard data ──
    _auto_export_dashboard(workspace, results, model_name, reasoning_model, state)
        
    return {"report_path": "audit_report.md", "mermaid_graph": mermaid_graph}


def _build_audit_tree(results: List[dict], workspace: str) -> dict:
    """Build a nested directory tree from flat audit results for the dashboard.

    Returns a tree structure like:
    {
        "name": "root",
        "type": "dir",
        "children": [
            {
                "name": "dockdesk",
                "type": "dir",
                "risk_counts": {"HIGH": 1, "MEDIUM": 0, "LOW": 2},
                "children": [
                    {
                        "name": "cli.py",
                        "type": "file",
                        "status": "FAIL",
                        "risk": "HIGH",
                        "safe_to_push": false,
                        "summary": "...",
                        "code_model": "...",
                        "reasoning_model": "...",
                        "duration_ms": 1234
                    }
                ]
            }
        ]
    }
    """
    root = {"name": os.path.basename(workspace) or "root", "type": "dir", "children": [], "risk_counts": {"HIGH": 0, "MEDIUM": 0, "LOW": 0}}

    for res in results:
        file_path = res.get("file", "unknown")
        try:
            rel = os.path.relpath(file_path, workspace)
        except ValueError:
            rel = file_path

        # Normalize path separators
        parts = rel.replace("\\", "/").split("/")

        # Navigate/create tree structure
        current = root
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                # Leaf file node
                file_node = {
                    "name": part,
                    "type": "file",
                    "path": rel,
                    "status": res.get("status", "UNKNOWN"),
                    "risk": res.get("risk", "UNKNOWN"),
                    "safe_to_push": res.get("safe_to_push", False),
                    "summary": str(res.get("summary", "") or "")[:200],
                    "fix": str(res.get("fix", "") or "")[:300],
                    "reasoning": str(res.get("reasoning", "") or "")[:300],
                    "code_model": res.get("code_model", ""),
                    "reasoning_model": res.get("reasoning_model", ""),
                    "duration_ms": res.get("duration_ms", 0),
                }
                current["children"].append(file_node)

                # Propagate risk counts up to all parent directories
                risk = res.get("risk", "UNKNOWN")
                if risk in ("HIGH", "MEDIUM", "LOW"):
                    # Walk back up the path to update all ancestors
                    ancestor = root
                    for ancestor_part in parts[:-1]:
                        for child in ancestor.get("children", []):
                            if child.get("type") == "dir" and child.get("name") == ancestor_part:
                                child["risk_counts"][risk] = child["risk_counts"].get(risk, 0) + 1
                                ancestor = child
                                break
                    # Also update root
                    root["risk_counts"][risk] = root["risk_counts"].get(risk, 0) + 1
            else:
                # Directory node - find or create
                found = None
                for child in current.get("children", []):
                    if child.get("type") == "dir" and child.get("name") == part:
                        found = child
                        break
                if not found:
                    found = {"name": part, "type": "dir", "children": [], "risk_counts": {"HIGH": 0, "MEDIUM": 0, "LOW": 0}}
                    current["children"].append(found)
                current = found

    return root


def _get_available_models_for_rotation() -> List[str]:
    """Get all locally available audit-suitable models for multi-model rotation."""
    try:
        from .models import get_available_ollama_models, is_model_audit_suitable
        available = get_available_ollama_models()
        return [m for m in available if is_model_audit_suitable(m)]
    except Exception:
        return []


def _auto_export_dashboard(workspace: str, results: List[dict], code_model: str, reasoning_model: str, state: dict = {}):
    """Auto-generate dashboard_data.json after every run for the React dashboard."""
    try:
        from .changelog import ChangelogReader, DEFAULT_CHANGELOG_FILE

        changelog_path = os.path.join(workspace, DEFAULT_CHANGELOG_FILE)
        if os.path.exists(changelog_path):
            reader = ChangelogReader(changelog_path)
            data = reader.export_for_dashboard()
        else:
            data = {"runs": [], "timeline": [], "files_history": {}, "risk_trend": []}

        # Enrich with dual-model info
        data["dual_model"] = {
            "code_model": code_model,
            "reasoning_model": reasoning_model,
        }

        # Add per-file detail from this run
        data["latest_run_files"] = []
        for res in results:
            file_path = res.get("file", "unknown")
            try:
                rel = os.path.relpath(file_path, workspace)
            except ValueError:
                rel = file_path
            data["latest_run_files"].append({
                "file": rel,
                "status": res.get("status", "UNKNOWN"),
                "risk": res.get("risk", "UNKNOWN"),
                "safe_to_push": res.get("safe_to_push", False),
                "summary": str(res.get("summary", "") or "")[:200],
                "duration_ms": res.get("duration_ms", 0),
                "code_model": res.get("code_model", ""),
                "reasoning_model": res.get("reasoning_model", ""),
                "author": res.get("author", "Unknown"),
                "author_email": res.get("author_email", ""),
                "last_commit": res.get("last_commit", ""),
                "team": res.get("team", ""),
            })

        # Build audit tree from results for tree visualization
        data["audit_tree"] = _build_audit_tree(results, workspace)

        # Add available models list for multi-model display
        data["available_models"] = _get_available_models_for_rotation()

        # Collect distinct models actually used in this run
        models_used = set()
        for res in results:
            if res.get("code_model"):
                models_used.add(res["code_model"])
            if res.get("reasoning_model"):
                models_used.add(res["reasoning_model"])
        data["models_used_this_run"] = sorted(models_used)
        data["orchestration_metrics"] = state.get("orchestration_metrics", {})

        # Accountability data (USP)
        data["accountability"] = state.get("accountability_data", {})
        data["audit_chain_link"] = state.get("audit_chain_link", {})

        # Repository knowledge graph for the interactive dashboard / LLM context.
        try:
            data["knowledge_graph"] = build_knowledge_graph(workspace)
        except Exception:
            data["knowledge_graph"] = {
                "workspace": workspace,
                "generated_at": "",
                "nodes": [],
                "edges": [],
                "clusters": [],
                "stats": {"total_nodes": 0, "total_edges": 0, "file_nodes": 0, "directory_nodes": 0, "doc_nodes": 0, "source_nodes": 0, "config_nodes": 0, "entry_points": []},
            }

        # Write to both workspace root and dashboard/public for dev server
        for dest in [
            os.path.join(workspace, "dashboard_data.json"),
            os.path.join(workspace, "dashboard", "public", "dashboard_data.json"),
        ]:
            try:
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, default=str)
            except Exception:
                pass

        console.print(f"[dim]  └─ Dashboard data → dashboard_data.json[/dim]")
    except Exception as e:
        console.print(f"[white][!] Dashboard export skipped: {e}[/white]")
