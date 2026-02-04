# Using DockDesk in Other Repositories

## Step 1: Push DockDesk to GitHub

```bash
# Commit any pending changes
git add .
git commit -m "Update DockDesk action"

# Push to GitHub
git push origin main
```

## Step 2: Copy This Workflow to Other Repos

Create `.github/workflows/dockdesk-audit.yml` in any repository:

```yaml
name: DockDesk Documentation Audit

on:
  pull_request:
    branches: [main, master, develop]
  push:
    branches: [main, master]
  workflow_dispatch:
    inputs:
      model:
        description: 'Ollama model to use'
        required: false
        default: 'qwen2.5-coder:3b'
        type: choice
        options:
          - qwen2.5-coder:1.5b
          - qwen2.5-coder:3b
          - qwen2.5-coder:7b
          - codellama:7b

jobs:
  audit:
    name: Documentation Audit
    runs-on: ubuntu-latest
    
    services:
      ollama:
        image: ollama/ollama:latest
        ports:
          - 11434:11434
    
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0
      
      - name: Wait for Ollama Service
        run: |
          echo "Waiting for Ollama to be ready..."
          for i in {1..30}; do
            if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
              echo "Ollama is ready!"
              break
            fi
            echo "Attempt $i/30..."
            sleep 2
          done
      
      - name: Pull Ollama Model
        run: |
          MODEL="${{ github.event.inputs.model || 'qwen2.5-coder:3b' }}"
          echo "Pulling model: $MODEL"
          curl -X POST http://localhost:11434/api/pull \
            -d "{\"name\": \"$MODEL\"}" \
            -H "Content-Type: application/json"
          
          # Wait for pull to complete
          sleep 10
      
      - name: Run DockDesk Audit
        uses: dockdesk/auditor@v2
        with:
          model: ${{ github.event.inputs.model || 'qwen2.5-coder:3b' }}
          auto_tune: 'false'
          fail_on_risk: 'HIGH'
          output_format: 'md'
          auto_fix: 'false'
      
      - name: Upload Audit Report
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: dockdesk-audit-report
          path: audit_report.md
          retention-days: 30
      
      - name: Comment on PR (if applicable)
        if: github.event_name == 'pull_request' && always()
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            if (fs.existsSync('audit_report.md')) {
              const report = fs.readFileSync('audit_report.md', 'utf8');
              github.rest.issues.createComment({
                issue_number: context.issue.number,
                owner: context.repo.owner,
                repo: context.repo.repo,
                body: '## 🔍 DockDesk Audit Report\n\n' + report
              });
            }
```

## Step 3: Customize Settings

### Risk Levels
- `HIGH`: Only fail on critical mismatches
- `MEDIUM`: Moderate strictness
- `LOW`: Maximum scrutiny

### Models
- `qwen2.5-coder:1.5b`: Fastest (<5k LOC)
- `qwen2.5-coder:3b`: Default (5-10k LOC)
- `qwen2.5-coder:7b`: Thorough (10-50k LOC)

### Auto-tune
Set `auto_tune: 'true'` to let DockDesk pick the best model based on codebase size.

## Alternative: Use Specific Version/Tag

Instead of `@main`, use a specific release:

```yaml
- uses: srivatsa-source/dockdesk@v2.0
```

## Testing Locally

Before pushing, test the action locally with Docker:

```bash
docker build -t dockdesk .
docker run -v $(pwd):/workspace dockdesk
```

## Troubleshooting

### Action not found
- The action is published at: https://github.com/marketplace/actions/dockdesk-neural-auditor
- Use: `dockdesk/auditor@v2`

### Ollama service timeout
- Increase wait time in the "Wait for Ollama Service" step
- Some models are large and take time to pull

### Model pull fails
- Check Ollama service is running: `curl http://localhost:11434/api/tags`
- Try a smaller model first: `qwen2.5-coder:1.5b`
