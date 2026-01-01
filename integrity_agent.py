import os
import sys
import json
import argparse
import requests
from typing import Optional, Dict, Any
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

# Initialize Rich Console
console = Console()

class AlertSystem:
    """Human-in-the-loop alert system via Slack/Discord webhooks."""
    
    def __init__(self, slack_url: str = None, discord_url: str = None):
        self.slack_url = slack_url
        self.discord_url = discord_url
    
    def send_alert(self, risk: str, summary: str, details: str, pr_url: str = None):
        emoji = "🔴" if risk == "HIGH" else "🟠" if risk == "MEDIUM" else "🟢"
        
        # Slack Alert
        if self.slack_url:
            slack_payload = {
                "blocks": [
                    {
                        "type": "header",
                        "text": {"type": "plain_text", "text": f"{emoji} DockDesk Alert: Documentation Drift Detected"}
                    },
                    {
                        "type": "section",
                        "fields": [
                            {"type": "mrkdwn", "text": f"*Risk Level:*\n{risk}"},
                            {"type": "mrkdwn", "text": f"*Summary:*\n{summary}"}
                        ]
                    },
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"*Details:*\n{details[:500]}..."}
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "🔍 Review PR"},
                                "url": pr_url,
                                "style": "danger"
                            } if pr_url else {}
                        ]
                    }
                ]
            }
            try:
                requests.post(self.slack_url, json=slack_payload, timeout=10)
                console.print("[green]✓ Slack alert sent[/green]")
            except Exception as e:
                console.print(f"[yellow]Slack alert failed: {e}[/yellow]")
        
        # Discord Alert
        if self.discord_url:
            discord_payload = {
                "embeds": [{
                    "title": f"{emoji} DockDesk Alert: Documentation Drift",
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
                discord_payload["embeds"][0]["url"] = pr_url
            try:
                requests.post(self.discord_url, json=discord_payload, timeout=10)
                console.print("[green]✓ Discord alert sent[/green]")
            except Exception as e:
                console.print(f"[yellow]Discord alert failed: {e}[/yellow]")

class GitHubReporter:
    def __init__(self, token: str, repo_name: str, pr_number: int):
        self.enabled = bool(token and repo_name and pr_number)
        self.repo_name = repo_name
        self.pr_number = pr_number
        if self.enabled:
            self.g = Github(token)
            self.repo = self.g.get_repo(repo_name)
            self.pr = self.repo.get_pull(pr_number)

    def get_pr_url(self) -> str:
        return f"https://github.com/{self.repo_name}/pull/{self.pr_number}" if self.enabled else None

    def post_comment(self, report: str, self_healed_doc: Optional[str] = None, doc_file: str = None):
        if not self.enabled:
            return

        body = f"## 🛡️ DockDesk Integrity Report\n\n{report}"
        
        if self_healed_doc:
            # Add prominent one-click fix section
            body += f"\n\n---\n\n## ✨ One-Click Fix Available\n\n"
            body += f"**Action Required:** A human reviewer must approve this fix.\n\n"
            body += f"### Option 1: Apply via GitHub UI\n"
            body += f"Copy the fixed documentation below and update `{doc_file or 'your doc file'}`:\n\n"
            body += f"<details open><summary>📝 <b>Click to view the corrected documentation</b></summary>\n\n```markdown\n{self_healed_doc}\n```\n</details>\n\n"
            body += f"### Option 2: Apply via Terminal\n"
            body += f"```bash\n# Run this command to auto-apply the fix:\ngit checkout {self.pr.head.ref}\n# Then copy the content above to your doc file\n```\n\n"
            body += f"---\n\n"
            body += f"⚠️ **Human Review Required:** Please verify the suggested fix before merging.\n"
            body += f"React with 👍 to approve or 👎 to reject this suggestion."
        
        try:
            self.pr.create_issue_comment(body)
            console.print("[bold green]✓ Posted report to GitHub PR[/bold green]")
        except Exception as e:
            console.print(f"[bold red]✗ Failed to post to GitHub: {e}[/bold red]")

class DockGuard:
    def __init__(self, gemini_key: str = None, groq_key: str = None):
        self.gemini_client = genai.Client(api_key=gemini_key) if gemini_key else None
        self.groq_client = Groq(api_key=groq_key) if groq_key else None
        self.gemini_models = ['gemini-2.0-flash', 'gemini-1.5-flash']
        self.groq_models = ['llama-3.3-70b-versatile', 'llama3-70b-8192', 'mixtral-8x7b-32768']

    def _generate(self, prompt: str, response_schema: Any = None) -> Any:
        # Try Gemini first
        if self.gemini_client:
            config = types.GenerateContentConfig(
                response_mime_type="application/json" if response_schema else "text/plain"
            )
            for model in self.gemini_models:
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
                    console.print(f"[yellow]Gemini {model} failed: {e}[/yellow]")
                    continue

        # Fallback to Groq (Free Tier)
        if self.groq_client:
            console.print("[blue]Falling back to Groq (Llama)...[/blue]")
            json_instruction = "\n\nIMPORTANT: Return ONLY valid JSON, no markdown." if response_schema else ""
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

        raise RuntimeError("All AI providers failed. Check your API keys and quotas.")

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
    guard = DockGuard(gemini_key=gemini_key, groq_key=groq_key)
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
        
        # Show the fix in terminal with syntax highlighting
        if result.get('fixed_content'):
            console.print("\n[bold cyan]═══════════════════════════════════════════════════════════════[/bold cyan]")
            console.print("[bold green]✨ PROPOSED FIX (Copy this to your doc file):[/bold green]\n")
            console.print(Syntax(result.get('fixed_content'), "markdown", theme="monokai", line_numbers=True))
            console.print("[bold cyan]═══════════════════════════════════════════════════════════════[/bold cyan]\n")
            
            # Interactive terminal fix (only in local mode)
            if not pr_number and sys.stdin.isatty():
                if Confirm.ask("[bold yellow]Apply this fix automatically?[/bold yellow]"):
                    try:
                        with open(args.doc, 'w', encoding='utf-8') as f:
                            f.write(result.get('fixed_content'))
                        console.print(f"[bold green]✓ Fixed! Updated {args.doc}[/bold green]")
                        sys.exit(0)  # Success after fix
                    except Exception as e:
                        console.print(f"[bold red]✗ Failed to write fix: {e}[/bold red]")
        
        # GitHub Reporting
        reporter = None
        if pr_number and pr_number.isdigit():
            reporter = GitHubReporter(github_token, repo_name, int(pr_number))
            reporter.post_comment(
                report=f"**Risk:** {risk_level}\n\n{result.get('details')}",
                self_healed_doc=result.get('fixed_content'),
                doc_file=args.doc
            )
        else:
            console.print("[yellow]Skipping GitHub comment: PR_NUMBER not found or invalid.[/yellow]")
        
        # Human-in-the-loop Alerts (Slack/Discord)
        if slack_webhook or discord_webhook:
            alerts = AlertSystem(slack_url=slack_webhook, discord_url=discord_webhook)
            pr_url = reporter.get_pr_url() if reporter else None
            alerts.send_alert(
                risk=risk_level,
                summary=result.get('summary', 'Documentation drift detected'),
                details=result.get('details', ''),
                pr_url=pr_url
            )

        # Exit Code
        if args.fail_on_drift.lower() == 'true':
            sys.exit(1)
    else:
        console.print("[green]No drift detected. Documentation is up to date.[/green]")

if __name__ == "__main__":
    main()
