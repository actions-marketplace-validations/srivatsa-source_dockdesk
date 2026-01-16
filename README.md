# DockDesk

Universal AI-powered documentation drift detector. Automatically discovers documentation, works with any codebase, and provides one-click GitHub fixes.

## Overview

DockDesk is an AI agent that runs on every Pull Request to detect when code changes don't match documentation. It:

1. Auto-discovers all documentation (markdown, docstrings, JSDoc, Javadoc, etc.)
2. Analyzes code intent using Gemini 2.0 or Llama
3. Posts inline GitHub suggestions you can commit with one click

Works with any language, any codebase, with minimal configuration.

## Quick Start

### Step 1: Add the Workflow

Create `.github/workflows/dockdesk.yml`:

```yaml
name: DockDesk Audit

on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  audit:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Detect Changed Files
        id: changed-files
        uses: tj-actions/changed-files@v44
        with:
          files: |
            **/*.py
            **/*.js
            **/*.ts
            **/*.java
            **/*.go
            **/*.rs
            **/*.rb
            **/*.cpp
            **/*.cs
            **/*.swift
            **/*.kt

      - name: Run DockDesk
        if: steps.changed-files.outputs.any_changed == 'true'
        uses: srivatsa-source/dockdesk@main
        with:
          gemini_api_key: ${{ secrets.GEMINI_API_KEY }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
          github_repository: ${{ github.repository }}
          pr_number: ${{ github.event.pull_request.number }}
          code_files: ${{ steps.changed-files.outputs.all_changed_files }}
```

### Step 2: Add Secrets

In your repository, go to Settings > Secrets and variables > Actions:

| Secret | Required | Description |
|--------|----------|-------------|
| `GEMINI_API_KEY` | Yes | Get free at [aistudio.google.com](https://aistudio.google.com) |
| `GITHUB_TOKEN` | Yes | Automatically provided by GitHub Actions |
| `GROQ_API_KEY` | No | Free fallback: [console.groq.com](https://console.groq.com) |
| `SLACK_WEBHOOK` | No | For Slack alerts |
| `DISCORD_WEBHOOK` | No | For Discord alerts |

### Step 3: Open a Pull Request

DockDesk will automatically:
- Find all relevant documentation
- Analyze your code for intent
- Post inline suggestions if docs need updating

## Configuration

All inputs are optional except API keys:

```yaml
- uses: srivatsa-source/dockdesk@main
  with:
    # Required
    gemini_api_key: ${{ secrets.GEMINI_API_KEY }}
    github_token: ${{ secrets.GITHUB_TOKEN }}
    github_repository: ${{ github.repository }}
    pr_number: ${{ github.event.pull_request.number }}
    
    # Code files to analyze (from changed-files action)
    code_files: ${{ steps.changed-files.outputs.all_changed_files }}
    
    # Documentation discovery
    doc_file: 'AUTO'           # AUTO = discover all docs (default)
                               # Or specify: 'docs/API.md'
    
    # Behavior
    fail_on_drift: 'true'      # Block PR if drift detected
    
    # Fallback AI (free tier)
    groq_api_key: ${{ secrets.GROQ_API_KEY }}
    
    # Alerts
    slack_webhook: ${{ secrets.SLACK_WEBHOOK }}
    discord_webhook: ${{ secrets.DISCORD_WEBHOOK }}
```

## Documentation Discovery

DockDesk automatically finds and analyzes:

| Source | Examples |
|--------|----------|
| Markdown | `README.md`, `docs/*.md`, `wiki/**/*.md`, `.github/*.md` |
| Python Docstrings | Module, class, and function docstrings |
| JSDoc/TSDoc | `/** ... */` comments in JS/TS files |
| Javadoc | `/** ... */` comments in Java files |
| Go Doc | `// Comment` blocks before declarations |
| RST/AsciiDoc | `*.rst`, `*.adoc` files |

The agent intelligently matches docs to changed files based on:
- File and folder name similarity
- Keyword matching in content
- Documentation type priority (README > API docs > nested docs)

## Local Usage

Run DockDesk locally for instant feedback:

```bash
# Install dependencies
pip install -r requirements.txt

# Set API key
export GEMINI_API_KEY="your-key"

# Run on specific files
python integrity_agent.py --code src/auth.py src/api.py

# Specify doc file
python integrity_agent.py --code src/auth.py --doc docs/AUTH.md

# JSON output for CI/scripts
python integrity_agent.py --code src/*.py --json
```

When drift is detected in interactive mode, DockDesk offers to auto-fix your docs:

```
DockDesk Audit
Status: DRIFT DETECTED
Risk Level: HIGH
Issues Found: 2

Apply fixes automatically? [y/N]: y
Fixed README.md
Fixed docs/API.md
```

## Integrations

### Slack Alerts

```yaml
slack_webhook: ${{ secrets.SLACK_WEBHOOK }}
```

Receive notifications when HIGH or MEDIUM risk drift is detected.

### Discord Alerts

```yaml
discord_webhook: ${{ secrets.DISCORD_WEBHOOK }}
```

## How It Works

**1. Discovery**
- Scan workspace for all documentation
- Extract docstrings from code files
- Match docs to changed files by relevance

**2. Analysis**
- Extract code intent using Gemini 2.0
- Compare against all relevant documentation
- Identify contradictions, missing info, outdated examples

**3. Reporting**
- Post PR review with inline suggestion blocks
- One-click "Commit suggestion" in GitHub UI
- Alert via Slack/Discord if configured

## Outputs

The action provides these outputs for downstream steps:

| Output | Description |
|--------|-------------|
| `drift_detected` | `true` if documentation drift was found |
| `risk_level` | `HIGH`, `MEDIUM`, or `LOW` |
| `issues_count` | Number of drift issues found |

## AI Agent Integration

DockDesk works as a verification layer for AI coding agents:

```bash
# JSON mode for programmatic use
python integrity_agent.py --code generated_code.py --json
```

Returns structured output:

```json
{
  "has_drift": true,
  "risk_level": "HIGH",
  "summary": "Code implements guest access, but docs specify admin-only",
  "issues": [
    {
      "file_path": "README.md",
      "line_number": 42,
      "original_text": "Only administrators can access this endpoint",
      "suggested_text": "Both guests and administrators can access this endpoint",
      "severity": "HIGH",
      "description": "Access control changed from admin-only to include guests"
    }
  ],
  "fixed_docs": {
    "README.md": "# Full fixed content..."
  }
}
```

## License

MIT License - see [LICENSE](LICENSE)
