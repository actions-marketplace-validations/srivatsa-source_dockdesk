# 🚀 DockDesk Setup Guide

Welcome to DockDesk! This guide will walk you through setting up the semantic auditor for your project.

---

## Prerequisites

Before starting, ensure you have:

- **Python 3.11+** installed
- **Git** installed
- **8GB+ RAM** recommended for larger models

---

## Step 1: Install Ollama

DockDesk uses Ollama for local LLM inference. Install it based on your OS:

### macOS / Linux
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Windows
Download from: https://ollama.com/download/windows

### Verify Installation
```bash
ollama --version
```

---

## Step 2: Choose Your Model

DockDesk works best with code-specialized models. Choose based on your needs:

| Model | Size | Speed | Best For |
|-------|------|-------|----------|
| `qwen2.5-coder:1.5b` | 1GB | ⚡⚡⚡ | Quick checks, CI pipelines |
| `qwen2.5-coder:3b` | 2GB | ⚡⚡ | **Recommended default** |
| `qwen2.5-coder:7b` | 4GB | ⚡ | Detailed analysis |
| `codellama:7b` | 4GB | ⚡ | Alternative option |
| `qwen2.5-coder:14b` | 8GB | 🐢 | Enterprise thoroughness |

### Pull Your Chosen Model
```bash
# Recommended for most projects
ollama pull qwen2.5-coder:3b

# Or for larger codebases
ollama pull qwen2.5-coder:7b
```

### Let DockDesk Choose (Auto-Tune)
```bash
# DockDesk will analyze your codebase and select the best model
python auditor_slm.py --auto-tune
```

---

## Step 3: Install DockDesk

### Option A: Clone the Repository
```bash
git clone https://github.com/dockdesk/auditor.git
cd auditor
pip install -r requirements.txt
```

### Option B: Install via pip (coming soon)
```bash
pip install dockdesk
```

---

## Step 4: Run Your First Audit

Navigate to your project directory and run:

```bash
# Basic audit
python auditor_slm.py --workspace /path/to/your/project

# With auto model selection
python auditor_slm.py --workspace /path/to/your/project --auto-tune

# See all options
python auditor_slm.py --help
```

---

## Step 5: Set Up GitHub Actions (Recommended)

Add automated auditing to your CI/CD pipeline:

### 5.1 Copy the Workflow

Create `.github/workflows/dockdesk.yml` in your repository:

```yaml
name: DockDesk Audit

on:
  pull_request:
    branches: [main]

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Run DockDesk
        uses: dockdesk/auditor@v2
        with:
          model: qwen2.5-coder:3b
          fail_on_risk: HIGH
```

### 5.2 Customize for Your Needs

See `.github/workflows/dockdesk-example.yml` for advanced options including:
- Auto-fix mode
- SARIF output for VS Code
- PR commenting
- Custom model selection

---

## Step 6: IDE Integration (VS Code)

### Generate SARIF for Problems Panel

```bash
# Generate SARIF format for VS Code
python auditor_slm.py --format sarif --output audit.sarif
```

Then install the SARIF Viewer extension in VS Code to see issues inline.

### Quick Fix Commands

```bash
# Apply documentation fixes automatically
python auditor_slm.py --fix

# Preview what would be fixed (dry run)
python auditor_slm.py --fix --verbose
```

---

## Step 7: Set Up the Dashboard (Optional)

Visualize your audit history:

### 7.1 Export Data
```bash
python auditor_slm.py dashboard --export dashboard_data.json
```

### 7.2 Run Dashboard Locally
```bash
cd dashboard
npm install
npm run dev
```

### 7.3 Deploy to Vercel
```bash
cd dashboard
npm run build
npx vercel --prod
```

---

## Configuration File (Optional)

Create `dockdesk.yml` in your project root:

```yaml
# DockDesk Configuration
model: qwen2.5-coder:3b
auto_tune: false
auto_fix: false
fail_on_risk: HIGH
output_format: md
enable_changelog: true
```

---

## CLI Reference

```
Usage: auditor_slm.py [OPTIONS] [COMMAND]

Commands:
  audit         Run semantic audit (default)
  list-models   Show available audit models
  init          Create config file
  dashboard     View/export audit statistics

Options:
  --workspace, -w PATH    Workspace to audit (default: .)
  --model, -m MODEL       Ollama model to use
  --auto-tune             Auto-select model by LOC
  --fix                   Apply documentation fixes
  --fix-code              Also apply code fixes
  --format, -f FORMAT     Output: md, json, sarif
  --output, -o FILE       Output file path
  --ci                    CI mode (non-interactive)
  --fail-on-risk LEVEL    Fail threshold: HIGH, MEDIUM, LOW
  --skip-rag              Skip RAG for faster audits
  --verbose, -v           Verbose output
```

---

## Troubleshooting

### Ollama Not Starting
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama manually
ollama serve
```

### Model Too Slow
- Try a smaller model: `--model qwen2.5-coder:1.5b`
- Skip RAG: `--skip-rag`
- Use `--auto-tune` to let DockDesk optimize

### Out of Memory
- Use smaller model (1.5b or 3b)
- Close other applications
- Consider upgrading RAM for 7b+ models

### No Changes Detected
- DockDesk uses git diff to scope audits
- Run `git status` to see if changes exist
- Use `--force-full-scan` to audit all files

---

## Next Steps

1. ⭐ Star the repo: https://github.com/dockdesk/auditor
2. 📖 Read the full documentation
3. 🐛 Report issues on GitHub
4. 💬 Join our Discord community

---

**Happy Auditing! 🛡️**
