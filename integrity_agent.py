"""
DockDesk Integrity Agent - Universal Documentation Drift Detector

An AI-powered agent that auto-discovers documentation across any codebase,
detects semantic inconsistencies between code and docs, and provides
one-click GitHub suggestion fixes.

Works with any programming language and documentation format.
"""

import os
import sys
import re
import ast
import json
import glob
import time
import argparse
import requests
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from google import genai
from google.genai import types
from groq import Groq
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.status import Status
from rich.syntax import Syntax
from rich.prompt import Confirm
from github import Github

console = Console()


@dataclass
class DocumentationSource:
    """Represents a discovered documentation source."""
    path: str
    content: str
    doc_type: str  # 'markdown', 'docstring', 'comment', 'rst', 'asciidoc'
    language: Optional[str] = None
    line_start: int = 1
    line_end: int = 0


@dataclass
class DriftIssue:
    """Represents a detected drift issue with fix suggestion."""
    file_path: str
    line_number: int
    original_text: str
    suggested_text: str
    severity: str  # 'HIGH', 'MEDIUM', 'LOW'
    description: str


@dataclass
class AnalysisResult:
    """Complete analysis result with all drift issues."""
    has_drift: bool
    risk_level: str
    summary: str
    details: str
    issues: List[DriftIssue] = field(default_factory=list)
    fixed_docs: Dict[str, str] = field(default_factory=dict)


class DocumentationDiscovery:
    """
    Intelligent documentation discovery system.
    Finds all documentation sources in a codebase including:
    - Markdown files (*.md)
    - RST files (*.rst)
    - AsciiDoc files (*.adoc, *.asciidoc)
    - Docstrings in code files
    - JSDoc/TSDoc comments
    - Inline documentation comments
    """

    # Documentation file patterns by priority
    DOC_PATTERNS = [
        # High priority - explicit docs
        'README.md', 'readme.md', 'README.MD',
        'DOCUMENTATION.md', 'documentation.md',
        'DOCS.md', 'docs.md',
        'API.md', 'api.md',
        'GUIDE.md', 'guide.md',
        'USAGE.md', 'usage.md',
        'CONTRIBUTING.md', 'contributing.md',
        # Docs folders
        'docs/**/*.md', 'doc/**/*.md', 'documentation/**/*.md',
        'wiki/**/*.md', '.github/**/*.md',
        # Nested READMEs
        '**/README.md',
        # RST documentation
        'docs/**/*.rst', '*.rst',
        # AsciiDoc
        'docs/**/*.adoc', '*.adoc', '*.asciidoc',
        # Any remaining markdown
        '**/*.md',
    ]

    # Code file patterns for docstring extraction
    CODE_PATTERNS = {
        'python': ['**/*.py'],
        'javascript': ['**/*.js', '**/*.jsx', '**/*.mjs'],
        'typescript': ['**/*.ts', '**/*.tsx'],
        'java': ['**/*.java'],
        'go': ['**/*.go'],
        'rust': ['**/*.rs'],
        'ruby': ['**/*.rb'],
        'csharp': ['**/*.cs'],
        'cpp': ['**/*.cpp', '**/*.hpp', '**/*.cc', '**/*.h'],
        'swift': ['**/*.swift'],
        'kotlin': ['**/*.kt', '**/*.kts'],
        'php': ['**/*.php'],
    }

    # Folders to exclude from search
    EXCLUDE_DIRS = {
        'node_modules', '.git', '__pycache__', '.venv', 'venv',
        'env', '.env', 'dist', 'build', 'target', '.tox',
        '.pytest_cache', '.mypy_cache', 'vendor', '.idea',
        '.vscode', 'coverage', '.next', '.nuxt', 'out'
    }

    def __init__(self, workspace_root: str = '.'):
        self.workspace_root = Path(workspace_root).resolve()

    def discover_all(self, extract_docstrings: bool = True) -> List[DocumentationSource]:
        """
        Discover all documentation sources in the workspace.
        
        Args:
            extract_docstrings: Whether to extract docstrings from code files
            
        Returns:
            List of DocumentationSource objects
        """
        docs = []
        seen_paths = set()

        # 1. Find documentation files (markdown, rst, asciidoc)
        for pattern in self.DOC_PATTERNS:
            for path in self._glob_with_exclusions(pattern):
                if path not in seen_paths:
                    seen_paths.add(path)
                    content = self._read_file(path)
                    if content:
                        doc_type = self._detect_doc_type(path)
                        docs.append(DocumentationSource(
                            path=str(path.relative_to(self.workspace_root)),
                            content=content,
                            doc_type=doc_type,
                            line_end=content.count('\n') + 1
                        ))

        # 2. Extract docstrings from code files if enabled
        if extract_docstrings:
            docstring_docs = self._extract_all_docstrings()
            docs.extend(docstring_docs)

        return docs

    def discover_relevant_docs(self, changed_files: List[str]) -> List[DocumentationSource]:
        """
        Discover documentation relevant to specific changed files.
        Uses intelligent matching to find related docs.
        """
        all_docs = self.discover_all(extract_docstrings=True)
        relevant = []

        # Get keywords from changed file paths and names
        keywords = set()
        for f in changed_files:
            path = Path(f)
            keywords.add(path.stem.lower())
            keywords.update(path.stem.lower().split('_'))
            keywords.update(path.stem.lower().split('-'))
            # Add parent folder names
            for part in path.parts[:-1]:
                keywords.add(part.lower())

        # Score each doc by relevance
        for doc in all_docs:
            score = 0
            doc_lower = doc.path.lower()
            content_lower = doc.content.lower()

            # Direct path match (highest priority)
            for cf in changed_files:
                cf_stem = Path(cf).stem.lower()
                if cf_stem in doc_lower:
                    score += 10

            # Keyword matches in path
            for kw in keywords:
                if len(kw) > 2 and kw in doc_lower:
                    score += 5

            # Keyword matches in content
            for kw in keywords:
                if len(kw) > 2 and kw in content_lower:
                    score += 1

            # Priority docs (README, API docs) always included
            if any(p in doc.path.lower() for p in ['readme', 'api', 'usage', 'guide']):
                score += 3

            if score > 0:
                relevant.append((score, doc))

        # Sort by score and return top docs
        relevant.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in relevant[:10]]  # Limit to top 10 most relevant

    def _glob_with_exclusions(self, pattern: str) -> List[Path]:
        """Glob with directory exclusions."""
        results = []
        for path in self.workspace_root.glob(pattern):
            if not any(excl in path.parts for excl in self.EXCLUDE_DIRS):
                if path.is_file():
                    results.append(path)
        return results

    def _read_file(self, path: Path) -> Optional[str]:
        """Safely read a file."""
        try:
            return path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            return None

    def _detect_doc_type(self, path: Path) -> str:
        """Detect documentation type from file extension."""
        suffix = path.suffix.lower()
        type_map = {
            '.md': 'markdown',
            '.rst': 'rst',
            '.adoc': 'asciidoc',
            '.asciidoc': 'asciidoc',
            '.txt': 'text',
        }
        return type_map.get(suffix, 'markdown')

    def _extract_all_docstrings(self) -> List[DocumentationSource]:
        """Extract docstrings from all supported code files."""
        docs = []

        for lang, patterns in self.CODE_PATTERNS.items():
            for pattern in patterns:
                for path in self._glob_with_exclusions(pattern):
                    content = self._read_file(path)
                    if content:
                        docstrings = self._extract_docstrings(content, lang, path)
                        docs.extend(docstrings)

        return docs

    def _extract_docstrings(self, content: str, language: str, path: Path) -> List[DocumentationSource]:
        """Extract docstrings from a code file."""
        docs = []
        rel_path = str(path.relative_to(self.workspace_root))

        if language == 'python':
            docs.extend(self._extract_python_docstrings(content, rel_path))
        elif language in ('javascript', 'typescript'):
            docs.extend(self._extract_jsdoc_comments(content, rel_path))
        elif language == 'java':
            docs.extend(self._extract_javadoc_comments(content, rel_path))
        elif language == 'go':
            docs.extend(self._extract_go_doc_comments(content, rel_path))

        return docs

    def _extract_python_docstrings(self, content: str, path: str) -> List[DocumentationSource]:
        """Extract Python docstrings using AST."""
        docs = []
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    docstring = ast.get_docstring(node)
                    if docstring and len(docstring) > 20:  # Skip trivial docstrings
                        name = getattr(node, 'name', 'module')
                        line = getattr(node, 'lineno', 1)
                        docs.append(DocumentationSource(
                            path=f"{path}::{name}",
                            content=docstring,
                            doc_type='docstring',
                            language='python',
                            line_start=line,
                            line_end=line + docstring.count('\n')
                        ))
        except SyntaxError:
            pass
        return docs

    def _extract_jsdoc_comments(self, content: str, path: str) -> List[DocumentationSource]:
        """Extract JSDoc/TSDoc comments."""
        docs = []
        pattern = r'/\*\*\s*([\s\S]*?)\*/'
        for i, match in enumerate(re.finditer(pattern, content)):
            docstring = match.group(1).strip()
            if len(docstring) > 20:
                line = content[:match.start()].count('\n') + 1
                docs.append(DocumentationSource(
                    path=f"{path}::jsdoc_{i}",
                    content=docstring,
                    doc_type='jsdoc',
                    language='javascript',
                    line_start=line,
                    line_end=line + docstring.count('\n')
                ))
        return docs

    def _extract_javadoc_comments(self, content: str, path: str) -> List[DocumentationSource]:
        """Extract Javadoc comments."""
        docs = []
        pattern = r'/\*\*\s*([\s\S]*?)\*/'
        for i, match in enumerate(re.finditer(pattern, content)):
            docstring = match.group(1).strip()
            if len(docstring) > 20:
                line = content[:match.start()].count('\n') + 1
                docs.append(DocumentationSource(
                    path=f"{path}::javadoc_{i}",
                    content=docstring,
                    doc_type='javadoc',
                    language='java',
                    line_start=line,
                    line_end=line + docstring.count('\n')
                ))
        return docs

    def _extract_go_doc_comments(self, content: str, path: str) -> List[DocumentationSource]:
        """Extract Go doc comments (// comments before declarations)."""
        docs = []
        # Match consecutive // comments followed by func/type/var/const
        pattern = r'((?://[^\n]*\n)+)\s*(?:func|type|var|const)\s+(\w+)'
        for match in re.finditer(pattern, content):
            comment_block = match.group(1)
            name = match.group(2)
            # Clean up the comment
            lines = [line.lstrip('/ ') for line in comment_block.strip().split('\n')]
            docstring = '\n'.join(lines)
            if len(docstring) > 20:
                line = content[:match.start()].count('\n') + 1
                docs.append(DocumentationSource(
                    path=f"{path}::{name}",
                    content=docstring,
                    doc_type='godoc',
                    language='go',
                    line_start=line,
                    line_end=line + docstring.count('\n')
                ))
        return docs


class AlertSystem:
    """Human-in-the-loop alert system via Slack/Discord webhooks."""

    def __init__(self, slack_url: str = None, discord_url: str = None):
        self.slack_url = slack_url
        self.discord_url = discord_url

    def send_alert(self, risk: str, summary: str, details: str, pr_url: str = None):
        emoji = "🔴" if risk == "HIGH" else "🟠" if risk == "MEDIUM" else "🟢"

        if self.slack_url:
            self._send_slack(emoji, risk, summary, details, pr_url)

        if self.discord_url:
            self._send_discord(emoji, risk, summary, details, pr_url)

    def _send_slack(self, emoji: str, risk: str, summary: str, details: str, pr_url: str):
        payload = {
            "blocks": [
                {"type": "header", "text": {"type": "plain_text", "text": f"{emoji} DockDesk: Documentation Drift Detected"}},
                {"type": "section", "fields": [
                    {"type": "mrkdwn", "text": f"*Risk Level:*\n{risk}"},
                    {"type": "mrkdwn", "text": f"*Summary:*\n{summary}"}
                ]},
                {"type": "section", "text": {"type": "mrkdwn", "text": f"*Details:*\n{details[:500]}..."}}
            ]
        }
        if pr_url:
            payload["blocks"].append({
                "type": "actions",
                "elements": [{"type": "button", "text": {"type": "plain_text", "text": "🔍 Review PR"}, "url": pr_url, "style": "danger"}]
            })
        try:
            requests.post(self.slack_url, json=payload, timeout=10)
            console.print("[green]✓ Slack alert sent[/green]")
        except Exception as e:
            console.print(f"[yellow]Slack alert failed: {e}[/yellow]")

    def _send_discord(self, emoji: str, risk: str, summary: str, details: str, pr_url: str):
        payload = {
            "embeds": [{
                "title": f"{emoji} DockDesk: Documentation Drift",
                "color": 0xFF0000 if risk == "HIGH" else 0xFFA500 if risk == "MEDIUM" else 0x00FF00,
                "fields": [
                    {"name": "Risk Level", "value": risk, "inline": True},
                    {"name": "Summary", "value": summary, "inline": False},
                    {"name": "Details", "value": details[:1000], "inline": False}
                ],
                "footer": {"text": "DockDesk Integrity Agent"}
            }]
        }
        if pr_url:
            payload["embeds"][0]["url"] = pr_url
        try:
            requests.post(self.discord_url, json=payload, timeout=10)
            console.print("[green]✓ Discord alert sent[/green]")
        except Exception as e:
            console.print(f"[yellow]Discord alert failed: {e}[/yellow]")


class GitHubReporter:
    """
    GitHub PR reporter with one-click suggestion fixes.
    Uses GitHub's suggestion syntax for inline fixes.
    """

    def __init__(self, token: str, repo_name: str, pr_number: int):
        self.enabled = bool(token and repo_name and pr_number)
        self.repo_name = repo_name
        self.pr_number = pr_number
        if self.enabled:
            self.g = Github(token)
            self.repo = self.g.get_repo(repo_name)
            self.pr = self.repo.get_pull(pr_number)
            self.head_sha = self.pr.head.sha

    def get_pr_url(self) -> str:
        return f"https://github.com/{self.repo_name}/pull/{self.pr_number}" if self.enabled else None

    def post_review_with_suggestions(self, result: AnalysisResult):
        """
        Post a PR review with inline suggestion comments.
        This enables one-click "Commit suggestion" in GitHub UI.
        """
        if not self.enabled:
            return

        # Build review comments with suggestions
        review_comments = []
        for issue in result.issues:
            if issue.suggested_text and issue.line_number > 0:
                # Create suggestion comment
                body = f"### 🛡️ DockDesk: {issue.severity} Priority Fix\n\n"
                body += f"{issue.description}\n\n"
                body += f"```suggestion\n{issue.suggested_text}\n```"

                review_comments.append({
                    'path': issue.file_path,
                    'line': issue.line_number,
                    'body': body
                })

        # Post the review
        try:
            if review_comments:
                # Create a review with inline comments
                review_body = self._build_summary_comment(result)
                self.pr.create_review(
                    body=review_body,
                    event='COMMENT',
                    comments=review_comments
                )
                console.print(f"[bold green]✓ Posted review with {len(review_comments)} inline suggestions[/bold green]")
            else:
                # No inline suggestions possible, post summary comment
                self.post_summary_comment(result)
        except Exception as e:
            console.print(f"[yellow]Review failed, falling back to comment: {e}[/yellow]")
            self.post_summary_comment(result)

    def post_summary_comment(self, result: AnalysisResult):
        """Post a summary comment with full fixed documentation."""
        if not self.enabled:
            return

        body = self._build_summary_comment(result)

        # Add full fixed docs if available
        if result.fixed_docs:
            body += "\n\n---\n\n## 📝 Full Fixed Documentation\n\n"
            for doc_path, fixed_content in result.fixed_docs.items():
                body += f"<details>\n<summary><b>📄 {doc_path}</b> (click to expand)</summary>\n\n"
                body += f"```markdown\n{fixed_content}\n```\n\n</details>\n\n"

        body += "\n---\n⚠️ **Human Review Required:** Please verify suggestions before committing.\n"
        body += "React with 👍 to approve or 👎 to request changes."

        try:
            self.pr.create_issue_comment(body)
            console.print("[bold green]✓ Posted summary comment to PR[/bold green]")
        except Exception as e:
            console.print(f"[bold red]✗ Failed to post comment: {e}[/bold red]")

    def _build_summary_comment(self, result: AnalysisResult) -> str:
        """Build the summary comment body."""
        emoji = "🔴" if result.risk_level == "HIGH" else "🟠" if result.risk_level == "MEDIUM" else "🟢"

        body = f"## 🛡️ DockDesk Integrity Report\n\n"
        body += f"| Status | Risk | Issues Found |\n"
        body += f"|--------|------|-------------|\n"
        body += f"| {'❌ Drift Detected' if result.has_drift else '✅ Verified'} | {emoji} {result.risk_level} | {len(result.issues)} |\n\n"
        body += f"### Summary\n{result.summary}\n\n"

        if result.details:
            body += f"### Details\n{result.details}\n\n"

        if result.issues:
            body += "### Issues Found\n\n"
            for i, issue in enumerate(result.issues, 1):
                body += f"**{i}. [{issue.severity}]** `{issue.file_path}` (line {issue.line_number})\n"
                body += f"   > {issue.description}\n\n"

        return body


class DockGuard:
    """
    Universal AI-powered documentation drift detector.
    Works with any programming language and documentation format.
    """

    def __init__(self, gemini_key: str = None, groq_key: str = None):
        self.gemini_client = genai.Client(api_key=gemini_key) if gemini_key else None
        self.groq_client = Groq(api_key=groq_key) if groq_key else None
        self.gemini_models = ['gemini-2.0-flash', 'gemini-1.5-flash']
        self.groq_models = ['llama-3.3-70b-versatile', 'llama3-70b-8192', 'mixtral-8x7b-32768']

    def _generate(self, prompt: str, response_schema: Any = None) -> Any:
        """Generate response from AI, with fallback between providers and retry logic."""
        last_error = None
        
        # Try Gemini first with retry logic for rate limits
        if self.gemini_client:
            config = types.GenerateContentConfig(
                response_mime_type="application/json" if response_schema else "text/plain"
            )
            for model in self.gemini_models:
                # Retry up to 3 times with exponential backoff for rate limits
                for attempt in range(3):
                    try:
                        response = self.gemini_client.models.generate_content(
                            model=model,
                            contents=prompt,
                            config=config
                        )
                        if response_schema:
                            return json.loads(response.text)
                        return response.text
                    except Exception as e:
                        last_error = e
                        error_str = str(e).lower()
                        # Check if it's a rate limit error
                        if '429' in str(e) or 'resource_exhausted' in error_str or 'quota' in error_str:
                            if attempt < 2:  # Don't wait on last attempt
                                wait_time = (attempt + 1) * 5  # 5s, 10s
                                console.print(f"[yellow]Gemini {model} rate limited, waiting {wait_time}s (attempt {attempt + 1}/3)...[/yellow]")
                                time.sleep(wait_time)
                                continue
                        console.print(f"[yellow]Gemini {model} failed: {e}[/yellow]")
                        break  # Move to next model

        # Fallback to Groq
        if self.groq_client:
            console.print("[blue]Falling back to Groq (Llama)...[/blue]")
            json_instruction = "\n\nIMPORTANT: Return ONLY valid JSON, no markdown code blocks." if response_schema else ""
            for model in self.groq_models:
                try:
                    response = self.groq_client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt + json_instruction}],
                        response_format={"type": "json_object"} if response_schema else None
                    )
                    result = response.choices[0].message.content
                    if response_schema:
                        return json.loads(result)
                    return result
                except Exception as e:
                    console.print(f"[yellow]Groq {model} failed: {e}[/yellow]")
                    continue
        else:
            console.print("[yellow]Groq API key not configured. Add GROQ_API_KEY secret for fallback.[/yellow]")

        # Provide helpful error message
        error_msg = "All AI providers failed. "
        if not self.groq_client:
            error_msg += "TIP: Add GROQ_API_KEY secret for free fallback (https://console.groq.com)."
        else:
            error_msg += "Check your API keys and quotas."
        raise RuntimeError(error_msg)

    def analyze(self, code_content: str, docs: List[DocumentationSource]) -> AnalysisResult:
        """
        Analyze code against all discovered documentation for drift.
        Returns structured result with line-specific fix suggestions.
        """
        # Combine all documentation for analysis
        docs_combined = "\n\n".join([
            f"--- DOCUMENT: {d.path} (type: {d.doc_type}) ---\n{d.content}"
            for d in docs
        ])

        # Step 1: Extract code intent
        with console.status("[bold blue]Step 1/3: Analyzing Code Intent...[/bold blue]"):
            intent_prompt = f"""
Analyze the following CODE CHANGES.
Identify the core LOGIC, RULES, BEHAVIORS, and API contracts being enforced.
Focus on "What does this code actually DO?" - ignore formatting/refactoring.

--- CODE ---
{code_content}
"""
            code_intent = self._generate(intent_prompt)

        # Step 2: Analyze each doc for drift with line-specific issues
        with console.status("[bold blue]Step 2/3: Detecting Documentation Drift...[/bold blue]"):
            analysis_prompt = f"""
You are a Senior Documentation Auditor. Compare the CODE INTENT against ALL DOCUMENTATION.

--- CODE INTENT (Ground Truth) ---
{code_intent}

--- ALL DOCUMENTATION ---
{docs_combined}

--- TASK ---
Find ALL inconsistencies between code and documentation:
1. Contradictions (docs say X, code does Y)
2. Missing information (code has features not documented)
3. Outdated examples (code samples that no longer work)
4. Incorrect API signatures, parameters, or return types

Return JSON:
{{
    "has_drift": true/false,
    "risk_level": "HIGH" | "MEDIUM" | "LOW",
    "summary": "Executive summary of all issues found",
    "details": "Detailed explanation of contradictions",
    "issues": [
        {{
            "file_path": "path/to/doc.md",
            "line_number": 42,
            "original_text": "The exact line that needs to change",
            "suggested_text": "The corrected line",
            "severity": "HIGH" | "MEDIUM" | "LOW",
            "description": "Why this is wrong and what the fix does"
        }}
    ]
}}

IMPORTANT:
- Include line numbers for each issue (estimate if unsure)
- Provide the EXACT original text and suggested fix
- Each issue should be a single line or small block that can be replaced
"""
            analysis = self._generate(analysis_prompt, response_schema=True)

        # Step 3: Generate full fixed docs if needed
        fixed_docs = {}
        if analysis.get('has_drift') and analysis.get('issues'):
            with console.status("[bold blue]Step 3/3: Generating Fixed Documentation...[/bold blue]"):
                # Group issues by file
                issues_by_file = {}
                for issue in analysis.get('issues', []):
                    fp = issue.get('file_path', '')
                    if fp not in issues_by_file:
                        issues_by_file[fp] = []
                    issues_by_file[fp].append(issue)

                # Generate fixed version for each affected doc
                for doc in docs:
                    if doc.path in issues_by_file or any(doc.path in fp for fp in issues_by_file):
                        fix_prompt = f"""
Given this documentation and the issues found, generate the COMPLETE FIXED documentation.

--- ORIGINAL DOCUMENTATION ({doc.path}) ---
{doc.content}

--- ISSUES TO FIX ---
{json.dumps(issues_by_file.get(doc.path, []), indent=2)}

--- CODE INTENT (Reference) ---
{code_intent}

Return ONLY the complete fixed documentation content, no JSON wrapper.
Preserve all formatting, structure, and sections. Only change what's necessary to fix the issues.
"""
                        fixed_content = self._generate(fix_prompt)
                        fixed_docs[doc.path] = fixed_content

        # Build result
        issues = [
            DriftIssue(
                file_path=i.get('file_path', ''),
                line_number=i.get('line_number', 0),
                original_text=i.get('original_text', ''),
                suggested_text=i.get('suggested_text', ''),
                severity=i.get('severity', 'MEDIUM'),
                description=i.get('description', '')
            )
            for i in analysis.get('issues', [])
        ]

        return AnalysisResult(
            has_drift=analysis.get('has_drift', False),
            risk_level=analysis.get('risk_level', 'LOW'),
            summary=analysis.get('summary', ''),
            details=analysis.get('details', ''),
            issues=issues,
            fixed_docs=fixed_docs
        )


def main():
    parser = argparse.ArgumentParser(description='DockDesk - Universal Documentation Drift Detector')
    parser.add_argument('--code', nargs='+', help="Path to code file(s) or 'AUTO' to scan workspace")
    parser.add_argument('--doc', default='AUTO', help="Path to doc file(s) or 'AUTO' to auto-discover")
    parser.add_argument('--workspace', default='.', help="Workspace root directory")
    parser.add_argument('--fail-on-drift', type=str, default="true", help="Exit with error if drift detected")
    parser.add_argument('--json', action='store_true', help="Output JSON for programmatic use")
    args = parser.parse_args()

    # Change to workspace directory for all file operations
    workspace_path = Path(args.workspace).resolve()
    if workspace_path.exists() and workspace_path.is_dir():
        os.chdir(workspace_path)
        console.print(f"[dim]Working directory: {workspace_path}[/dim]")
    else:
        console.print(f"[bold red]Error: Workspace directory not found: {args.workspace}[/bold red]")
        sys.exit(1)

    # Load environment
    gemini_key = os.getenv("GEMINI_API_KEY")
    groq_key = os.getenv("GROQ_API_KEY")
    github_token = os.getenv("GITHUB_TOKEN")
    repo_name = os.getenv("GITHUB_REPOSITORY")
    pr_number = os.getenv("PR_NUMBER")
    slack_webhook = os.getenv("SLACK_WEBHOOK")
    discord_webhook = os.getenv("DISCORD_WEBHOOK")

    if not gemini_key and not groq_key:
        console.print("[bold red]Error: No API key found. Set GEMINI_API_KEY or GROQ_API_KEY.[/bold red]")
        sys.exit(1)

    # Initialize discovery with current directory (already changed to workspace)
    discovery = DocumentationDiscovery('.')

    # Get code files
    code_files = []
    if args.code:
        for item in args.code:
            code_files.extend(item.split())
    
    # Handle AUTO mode - auto-discover code files in workspace
    if not code_files or code_files == ['AUTO'] or (len(code_files) == 1 and code_files[0].upper() == 'AUTO'):
        console.print("[cyan]Auto-discovering code files in workspace...[/cyan]")
        # Discover all code files in the workspace
        discovered_files = []
        for lang, patterns in discovery.CODE_PATTERNS.items():
            for pattern in patterns:
                for path in discovery._glob_with_exclusions(pattern):
                    discovered_files.append(str(path))
        
        if discovered_files:
            code_files = discovered_files[:50]  # Limit to 50 files to avoid overwhelming the AI
            console.print(f"[green]Found {len(discovered_files)} code file(s), analyzing top {len(code_files)}[/green]")
        else:
            console.print("[bold yellow]Warning: No code files found in workspace.[/bold yellow]")
            console.print("[dim]The workspace appears to be empty or contains no supported code files.[/dim]")
            sys.exit(0)

    # Read code content
    code_content = ""
    valid_files = []
    for path in code_files:
        # Skip if path is 'AUTO' (safety check)
        if path.upper() == 'AUTO':
            continue
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                code_content += f"\n--- FILE: {path} ---\n{content}\n"
                valid_files.append(path)
        except FileNotFoundError:
            console.print(f"[yellow]Warning: File not found: {path}[/yellow]")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not read {path}: {e}[/yellow]")

    if not code_content.strip():
        console.print("[bold red]Error: No valid code files to analyze.[/bold red]")
        sys.exit(1)

    console.print(f"[cyan]Analyzing {len(valid_files)} code file(s)...[/cyan]")

    # Discover documentation
    if args.doc == 'AUTO':
        console.print("[cyan]Auto-discovering documentation...[/cyan]")
        docs = discovery.discover_relevant_docs(valid_files)
        if not docs:
            # Fallback to all docs
            docs = discovery.discover_all(extract_docstrings=True)
        
        if not docs:
            console.print("[bold yellow]Warning: No documentation files found in workspace.[/bold yellow]")
            console.print("[dim]Consider creating a README.md or adding docstrings to your code.[/dim]")
            # Create a warning result
            result = AnalysisResult(
                has_drift=False,
                risk_level="LOW",
                summary="No documentation found to audit",
                details="The workspace has no markdown files, docstrings, or other documentation to compare against the code changes."
            )
        else:
            console.print(f"[green]Found {len(docs)} documentation source(s):[/green]")
            for doc in docs[:5]:  # Show first 5
                console.print(f"  [dim]• {doc.path} ({doc.doc_type})[/dim]")
            if len(docs) > 5:
                console.print(f"  [dim]... and {len(docs) - 5} more[/dim]")
            
            # Run analysis
            guard = DockGuard(gemini_key=gemini_key, groq_key=groq_key)
            try:
                result = guard.analyze(code_content, docs)
            except Exception as e:
                console.print(f"[bold red]Analysis Failed: {e}[/bold red]")
                sys.exit(1)
    else:
        # Specific doc file provided
        try:
            with open(args.doc, 'r', encoding='utf-8') as f:
                doc_content = f.read()
            docs = [DocumentationSource(
                path=args.doc,
                content=doc_content,
                doc_type='markdown'
            )]
            
            guard = DockGuard(gemini_key=gemini_key, groq_key=groq_key)
            result = guard.analyze(code_content, docs)
        except FileNotFoundError:
            console.print(f"[bold red]Error: Documentation file not found: {args.doc}[/bold red]")
            sys.exit(1)
        except Exception as e:
            console.print(f"[bold red]Analysis Failed: {e}[/bold red]")
            sys.exit(1)

    # JSON output mode
    if args.json:
        output = {
            "has_drift": result.has_drift,
            "risk_level": result.risk_level,
            "summary": result.summary,
            "details": result.details,
            "issues": [
                {
                    "file_path": i.file_path,
                    "line_number": i.line_number,
                    "original_text": i.original_text,
                    "suggested_text": i.suggested_text,
                    "severity": i.severity,
                    "description": i.description
                }
                for i in result.issues
            ],
            "fixed_docs": result.fixed_docs
        }
        print(json.dumps(output, indent=2))
        sys.exit(1 if result.has_drift and args.fail_on_drift.lower() == 'true' else 0)

    # Console output
    console.print(Panel.fit(
        f"[bold]Status:[/bold] {'[red]DRIFT DETECTED[/red]' if result.has_drift else '[green]INTEGRITY VERIFIED[/green]'}\n"
        f"[bold]Risk Level:[/bold] {result.risk_level}\n"
        f"[bold]Issues Found:[/bold] {len(result.issues)}\n"
        f"[bold]Summary:[/bold] {result.summary}",
        title="🛡️ DockDesk Audit",
        border_style="red" if result.has_drift else "green"
    ))

    if result.has_drift:
        console.print(Markdown(f"### Details\n{result.details}"))

        # Show issues
        if result.issues:
            console.print("\n[bold cyan]═══ Issues Found ═══[/bold cyan]\n")
            for i, issue in enumerate(result.issues, 1):
                emoji = "🔴" if issue.severity == "HIGH" else "🟠" if issue.severity == "MEDIUM" else "🟢"
                console.print(f"{emoji} [{issue.severity}] {issue.file_path}:{issue.line_number}")
                console.print(f"   {issue.description}")
                if issue.suggested_text:
                    console.print(f"   [green]Fix:[/green] {issue.suggested_text[:100]}...")
                console.print()

        # Show fixed docs
        if result.fixed_docs:
            console.print("\n[bold cyan]═══ Proposed Fixes ═══[/bold cyan]\n")
            for doc_path, fixed_content in result.fixed_docs.items():
                console.print(f"[bold green]📄 {doc_path}:[/bold green]")
                console.print(Syntax(fixed_content[:2000], "markdown", theme="monokai", line_numbers=True))
                if len(fixed_content) > 2000:
                    console.print("[dim]... (truncated)[/dim]")
                console.print()

            # Interactive fix in local mode
            if not pr_number and sys.stdin.isatty():
                if Confirm.ask("[bold yellow]Apply fixes automatically?[/bold yellow]"):
                    for doc_path, fixed_content in result.fixed_docs.items():
                        try:
                            with open(doc_path, 'w', encoding='utf-8') as f:
                                f.write(fixed_content)
                            console.print(f"[bold green]✓ Fixed {doc_path}[/bold green]")
                        except Exception as e:
                            console.print(f"[bold red]✗ Failed to write {doc_path}: {e}[/bold red]")
                    sys.exit(0)

        # GitHub reporting with one-click suggestions
        reporter = None
        if pr_number and pr_number.isdigit():
            reporter = GitHubReporter(github_token, repo_name, int(pr_number))
            reporter.post_review_with_suggestions(result)

        # Alerts
        if slack_webhook or discord_webhook:
            alerts = AlertSystem(slack_url=slack_webhook, discord_url=discord_webhook)
            alerts.send_alert(
                risk=result.risk_level,
                summary=result.summary,
                details=result.details,
                pr_url=reporter.get_pr_url() if reporter else None
            )

        # Exit code
        if args.fail_on_drift.lower() == 'true':
            sys.exit(1)
    else:
        console.print("[green]✅ No drift detected. Documentation is in sync with code.[/green]")


if __name__ == "__main__":
    main()
