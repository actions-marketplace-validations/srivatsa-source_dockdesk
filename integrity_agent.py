import os
import sys
import json
import argparse
from typing import Optional, Dict, Any
from google import genai
from google.genai import types
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.status import Status
from github import Github

# Initialize Rich Console
console = Console()

class GitHubReporter:
    def __init__(self, token: str, repo_name: str, pr_number: int):
        self.enabled = bool(token and repo_name and pr_number)
        if self.enabled:
            self.g = Github(token)
            self.repo = self.g.get_repo(repo_name)
            self.pr = self.repo.get_pull(pr_number)

    def post_comment(self, report: str, self_healed_doc: Optional[str] = None):
        if not self.enabled:
            return

        body = f"## 🛡️ DockDesk Integrity Report\n\n{report}"
        
        if self_healed_doc:
            body += f"\n\n<details><summary>📝 <b>Proposed Documentation Fix</b> (Click to expand)</summary>\n\n```markdown\n{self_healed_doc}\n```\n</details>"
        
        try:
            self.pr.create_issue_comment(body)
            console.print("[bold green]✓ Posted report to GitHub PR[/bold green]")
        except Exception as e:
            console.print(f"[bold red]✗ Failed to post to GitHub: {e}[/bold red]")

class DockGuard:
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        # Fallback list of models
        self.models = ['gemini-2.0-flash', 'gemini-2.0-flash-001', 'gemini-1.5-flash']

    def _generate(self, prompt: str, response_schema: Any = None) -> Any:
        config = types.GenerateContentConfig(
            response_mime_type="application/json" if response_schema else "text/plain"
        )
        
        for model in self.models:
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config
                )
                if response_schema:
                    return json.loads(response.text)
                return response.text
            except Exception:
                continue
        raise RuntimeError("All Gemini models failed.")

    def analyze(self, code_content: str, doc_content: str) -> Dict[str, Any]:
        # Step 1: Intent Extraction (Chain of Thought)
        with console.status("[bold blue]Step 1/2: Analyzing Code Intent...[/bold blue]"):
            intent_prompt = f"""
            Analyze the following CODE CHANGES. 
            Identify the core LOGIC, RULES, and BEHAVIORS that are being enforced.
            Ignore formatting/refactoring. Focus on "What does this code actually DO?".
            
            --- CODE ---
            {code_content}
            """
            code_intent = self._generate(intent_prompt)

        # Step 2: Verification against Docs
        with console.status("[bold blue]Step 2/2: Verifying Documentation Integrity...[/bold blue]"):
            verify_prompt = f"""
            You are a Senior Auditor. Compare the CODE INTENT against the DOCUMENTATION.
            
            --- CODE INTENT (Ground Truth) ---
            {code_intent}

            --- DOCUMENTATION ---
            {doc_content}

            --- TASK ---
            1. Does the documentation contradict the code intent?
            2. Is the documentation missing critical details present in the code?
            3. Are the code examples in the documentation still valid?

            Return JSON:
            {{
                "has_drift": true/false,
                "risk_level": "HIGH" | "MEDIUM" | "LOW",
                "summary": "Short executive summary of the issue",
                "details": "Detailed explanation of the contradiction",
                "fixed_content": "The full markdown content of the documentation file, corrected to match the code. Return null if no drift."
            }}
            """
            return self._generate(verify_prompt, response_schema=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--code', nargs='+', required=True, help="Path to code file(s)")
    parser.add_argument('--doc', required=True, help="Path to documentation file")
    parser.add_argument('--fail-on-drift', type=str, default="true")
    args = parser.parse_args()

    # Load Environment
    api_key = os.getenv("GEMINI_API_KEY")
    github_token = os.getenv("GITHUB_TOKEN")
    repo_name = os.getenv("GITHUB_REPOSITORY")
    pr_number = os.getenv("PR_NUMBER")

    if not api_key:
        console.print("[bold red]Error: GEMINI_API_KEY is missing.[/bold red]")
        sys.exit(1)

    # Read Files
    code_content = ""
    try:
        # Handle case where GitHub Actions passes multiple files as a single space-separated string
        file_paths = []
        for item in args.code:
            file_paths.extend(item.split())

        for path in file_paths:
            with open(path, 'r', encoding='utf-8') as f:
                code_content += f"\n--- FILE: {path} ---\n{f.read()}\n"
        
        with open(args.doc, 'r', encoding='utf-8') as f:
            doc_content = f.read()
    except FileNotFoundError as e:
        console.print(f"[bold red]File not found: {e}[/bold red]")
        sys.exit(1)

    # Run Analysis
    guard = DockGuard(api_key)
    try:
        result = guard.analyze(code_content, doc_content)
    except Exception as e:
        console.print(f"[bold red]Analysis Failed: {e}[/bold red]")
        sys.exit(1)

    # Report Results
    has_drift = result.get("has_drift", False)
    risk_level = result.get("risk_level", "LOW")
    
    # Console Output
    console.print(Panel.fit(
        f"[bold]Status:[/bold] {'[red]DRIFT DETECTED[/red]' if has_drift else '[green]INTEGRITY VERIFIED[/green]'}\n"
        f"[bold]Risk Level:[/bold] {risk_level}\n"
        f"[bold]Summary:[/bold] {result.get('summary')}",
        title="DockDesk Audit",
        border_style="red" if has_drift else "green"
    ))

    if has_drift:
        console.print(Markdown(f"### Details\n{result.get('details')}"))
        
        # GitHub Reporting
        if pr_number and pr_number.isdigit():
            reporter = GitHubReporter(github_token, repo_name, int(pr_number))
            reporter.post_comment(
                report=f"**Risk:** {risk_level}\n\n{result.get('details')}",
                self_healed_doc=result.get('fixed_content')
            )

        # Exit Code
        if args.fail_on_drift.lower() == 'true':
            sys.exit(1)

if __name__ == "__main__":
    main()
