"""
GitHub Lens & Local Heuristic Fallback for DockDesk.

Provides robust, fault-tolerant analysis of code vs. documentation drift.
Uses the GitHub API (via PyGithub) when connected, or falls back to local AST and Git
analyses when offline or disconnected.
"""

import os
import re
import ast
import subprocess
from typing import Dict, List, Optional

# Attempt PyGithub import, handles missing dependency gracefully
try:
    from github import Github
except ImportError:
    Github = None


def get_github_repo_name(workspace: str) -> Optional[str]:
    """Extract owner/repo from Git remote URL if it exists and points to GitHub."""
    try:
        import git
        repo = git.Repo(workspace, search_parent_directories=True)
        for remote in repo.remotes:
            for url in remote.urls:
                if "github.com" in url:
                    # Parse formats like:
                    # https://github.com/owner/repo.git
                    # git@github.com:owner/repo.git
                    clean_url = url.split("github.com")[-1].strip("/:").replace(".git", "")
                    parts = clean_url.split("/")
                    if len(parts) >= 2:
                        return f"{parts[-2]}/{parts[-1]}"
    except Exception:
        pass
    return None


def run_github_lens(file_path: str, workspace: str) -> Optional[Dict]:
    """Query GitHub API to analyze recent commit log keywords and issues/PRs for this file."""
    if not Github:
        return None

    repo_name = get_github_repo_name(workspace)
    if not repo_name:
        return None

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    try:
        # Initialize GitHub client (authenticated if token provided)
        g = Github(token) if token else Github()
        repo = g.get_repo(repo_name)
        rel_path = os.path.relpath(file_path, workspace).replace("\\", "/")

        findings = []
        commit_messages = []
        
        # 1. Fetch recent commits for the file
        try:
            commits = repo.get_commits(path=rel_path)
            for commit in commits[:5]:
                commit_messages.append(commit.commit.message)
        except Exception:
            pass

        # 2. Search issues and PRs mentioning the file
        try:
            query = f"repo:{repo_name} {os.path.basename(file_path)}"
            issues = g.search_issues(query)
            for issue in issues[:3]:
                # Look for documentation-related keywords in title or body
                body_text = issue.body.lower() if issue.body else ""
                title_text = issue.title.lower()
                if "doc" in body_text or "doc" in title_text or "outdated" in body_text or "drift" in body_text:
                    findings.append(f"GitHub Issue #{issue.number} mentions doc/drift: {issue.title}")
        except Exception:
            pass

        # 3. Analyze commit messages for doc modification trends
        doc_commit_count = sum(1 for msg in commit_messages if any(k in msg.lower() for k in ["doc", "readme", "comment"]))
        code_commit_count = sum(1 for msg in commit_messages if any(k in msg.lower() for k in ["refactor", "feat", "fix", "signature", "param"]))

        if code_commit_count > 0 and doc_commit_count == 0:
            findings.append(
                f"GitHub History: Last {len(commit_messages)} commits contain code changes but 0 documentation updates."
            )

        if findings:
            return {
                "status": "FAIL",
                "risk": "MEDIUM",
                "summary": "GitHub Lens identified potential documentation drift or open issues.",
                "findings": findings,
                "draft_fix": f"Review recent commits and documentation changes for {rel_path}.",
                "safe_to_push": False
            }

    except Exception:
        # Gracefully handle API rate limits or connection failures
        pass

    return None


def run_local_heuristic_lens(file_path: str, workspace: str, code_content: str, docs_text: str) -> Dict:
    """Analyze file contents offline using Python AST and local Git history."""
    findings = []
    suggested_fixes = []
    rel_path = os.path.relpath(file_path, workspace).replace("\\", "/")

    # 1. Query local git log if git repository
    try:
        import git
        repo = git.Repo(workspace, search_parent_directories=True)
        local_commits = list(repo.iter_commits(paths=rel_path, max_count=5))
        code_keywords = ["refactor", "feat", "fix", "signature", "param", "change"]
        doc_keywords = ["doc", "readme", "comment", "inline"]
        
        has_code_change = False
        has_doc_change = False
        
        for c in local_commits:
            msg = c.message.lower()
            if any(k in msg for k in code_keywords):
                has_code_change = True
            if any(k in msg for k in doc_keywords):
                has_doc_change = True
                
        if has_code_change and not has_doc_change:
            findings.append("Local Git log shows recent code signature/refactor changes with no documented changes.")
    except Exception:
        pass

    # 2. Perform AST signature validation on Python files
    if file_path.endswith(".py") and code_content:
        try:
            tree = ast.parse(code_content)
            functions = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    docstring = ast.get_docstring(node)
                    args = [arg.arg for arg in node.args.args if arg.arg != "self"]
                    functions.append({
                        "name": node.name,
                        "args": args,
                        "docstring": docstring,
                        "lineno": node.lineno
                    })

            for func in functions:
                if func["docstring"]:
                    # Compare actual arguments vs. documented params in docstring
                    missing_args = [arg for arg in func["args"] if arg not in func["docstring"]]
                    if missing_args:
                        findings.append(
                            f"Python AST: Function '{func['name']}' has undocumented arguments {missing_args}."
                        )
                        suggested_fixes.append(
                            f"Add explanation for parameters {missing_args} in function '{func['name']}' docstring."
                        )
                else:
                    # Public function missing docstring
                    if not func["name"].startswith("_"):
                        findings.append(f"Python AST: Public function '{func['name']}' is missing a docstring.")
                        suggested_fixes.append(f"Add docstring to public function '{func['name']}'.")
        except Exception:
            pass

    # 3. Perform JS/TS JSDoc check
    if any(file_path.endswith(ext) for ext in [".js", ".jsx", ".ts", ".tsx"]):
        # Regex search for exported functions/methods
        exports = re.findall(r'export\s+(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)', code_content)
        for func_name, params_str in exports:
            params = [p.strip().split(":")[0].strip() for p in params_str.split(",") if p.strip()]
            # Find JSDoc comments before the export
            func_esc = re.escape(func_name)
            pattern = rf'(/\*\*[\s\S]*?\*/)\s*(?:export\s+)?(?:async\s+)?function\s+{func_esc}'
            jsdoc_match = re.search(pattern, code_content)
            if jsdoc_match:
                jsdoc = jsdoc_match.group(1)
                missing_params = [p for p in params if p and f"@param {p}" not in jsdoc and f"@param {{{p}}}" not in jsdoc]
                if missing_params:
                    findings.append(f"JSDoc Lint: Function '{func_name}' has undocumented parameters {missing_params}.")
                    suggested_fixes.append(f"Add @param tags for parameters {missing_params} to function '{func_name}' JSDoc.")
            else:
                findings.append(f"JSDoc Lint: Exported function '{func_name}' is missing JSDoc comments.")
                suggested_fixes.append(f"Create JSDoc block for exported function '{func_name}'.")

    # 4. Scan for common drift flags (TODO, FIXME, deprecation mismatch)
    for idx, line in enumerate(code_content.splitlines(), 1):
        if "TODO" in line:
            findings.append(f"TODO tag on line {idx}: {line.strip()}")
        if "FIXME" in line:
            findings.append(f"FIXME tag on line {idx}: {line.strip()}")
        if "@deprecated" in line or "deprecated" in line.lower():
            if docs_text and "deprecated" not in docs_text.lower():
                findings.append(f"Deprecation mismatch: Code has deprecation marker on line {idx} but docs do not mention it.")
                suggested_fixes.append("Update docs to reflect function deprecation.")

    # 5. Compile into a standard result payload
    if findings:
        status = "FAIL"
        risk = "HIGH" if any("AST:" in f or "JSDoc:" in f for f in findings) else "MEDIUM"
        summary = f"Local Heuristic Lens detected {len(findings)} potential documentation/AST mismatches."
        fix = "\n".join(suggested_fixes) if suggested_fixes else "Update documentation to describe active functions and parameters."
    else:
        status = "PASS"
        risk = "LOW"
        summary = "No documentation drift or AST mismatches detected by Local Heuristic Lens."
        fix = ""

    return {
        "status": status,
        "risk": risk,
        "summary": summary,
        "findings": findings,
        "fix": fix,
        "draft_fix": fix,
        "safe_to_push": status == "PASS" or risk == "LOW"
    }


def identify_problems(file_path: str, workspace: str, code_content: str, docs_text: str) -> Dict:
    """Identify issues in a file using GitHub Lens (with automatic Local Heuristic fallback)."""
    # Try GitHub Lens online scan first
    github_result = run_github_lens(file_path, workspace)
    if github_result:
        github_result["code_model"] = "GitHub Lens"
        github_result["reasoning_model"] = "GitHub Lens"
        return github_result

    # Fall back to Local Heuristic scan
    local_result = run_local_heuristic_lens(file_path, workspace, code_content, docs_text)
    local_result["code_model"] = "Local Heuristic Lens"
    local_result["reasoning_model"] = "Local Heuristic Lens"
    return local_result
