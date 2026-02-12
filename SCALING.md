# DockDesk Scaling Guide

How to audit repositories from small projects to massive monorepos.

## Quick Reference

| Repo Size | Files | Recommended Command |
|-----------|-------|---------------------|
| Small     | < 100  | `dockdesk audit --workspace /repo` |
| Medium    | 100–500 | `dockdesk audit -w /repo --fast` |
| Large     | 500–2000 | `dockdesk audit -w /repo --fast --max-files 200 --workers 4` |
| Monorepo  | 2000+  | `dockdesk audit -w /repo --fast --max-files 500 --workers 8 --include "src/**"` |

## Installation Methods

### pip install (recommended for testing on any repo)

```bash
# From the dockdesk directory:
pip install -e .

# Now use from anywhere:
dockdesk audit /path/to/any/repo

# With RAG support (adds ~800MB for torch):
pip install -e ".[rag]"
```

### Docker (isolated, no Python setup needed)

```bash
# Build once:
docker build -t dockdesk /path/to/dockdesk

# Run on any repo (Ollama must be running on host):
docker run -v /path/to/repo:/workspace dockdesk audit . --fast

# With docker compose (includes Ollama):
docker compose up ollama
docker compose exec ollama ollama pull qwen2.5-coder:3b
docker compose run dockdesk audit . --fast
```

## Performance Tuning

### `--fast` mode

Skips the DeepSeek reasoning step for LOW-risk files and batches analysis calls.
Typically **3–5x faster** with minimal quality loss on large repos.

```bash
dockdesk audit -w /repo --fast
```

### `--max-files N`

Caps the number of files analyzed. Files are selected by change recency (git diff) or discovery order.

```bash
dockdesk audit -w /repo --max-files 100
```

### `--workers N`

Parallel worker threads for LLM calls. Each worker sends requests to Ollama concurrently.
Default: auto (1 per Ollama endpoint).

```bash
dockdesk audit -w /repo --workers 4
```

### `--include` / `--exclude`

Glob patterns to focus on specific directories. Comma-separated.

```bash
# Only audit src/ and docs/
dockdesk audit -w /repo --include "src/**,docs/**"

# Skip generated code and vendor
dockdesk audit -w /repo --exclude "generated/**,vendor/**,*.min.js"
```

### `--max-file-size N`

Skip files larger than N bytes. Default: 512000 (500KB).

```bash
# Skip files over 100KB
dockdesk audit -w /repo --max-file-size 100000
```

### `--batch-size N`

Number of files per batched LLM call in fast mode. Default: 5.

```bash
dockdesk audit -w /repo --fast --batch-size 10
```

### `--ollama-urls`

Distribute inference across multiple Ollama instances for parallel throughput.

```bash
# Two local instances on different ports
dockdesk audit -w /repo --ollama-urls "http://localhost:11434,http://localhost:11435"

# Remote GPU server + local
dockdesk audit -w /repo --ollama-urls "http://gpu-server:11434,http://localhost:11434" --workers 8
```

### `--clear-cache`

Force re-analysis of all files (ignores cached results from previous runs).

```bash
dockdesk audit -w /repo --clear-cache
```

## Model Selection

### Auto-tune (recommended for unknown repos)

```bash
dockdesk audit -w /repo --auto-tune
```

Selects model based on codebase LOC:
- < 5K LOC → `qwen2.5-coder:1.5b` (fastest)
- < 50K LOC → `qwen2.5-coder:3b` (balanced)
- < 200K LOC → `qwen2.5-coder:7b` (thorough)
- 200K+ LOC → `codellama:7b` (large-scale)

### Reasoning model

The reasoning model (DeepSeek-R1) handles risk assessment and judgment.
For faster runs on large repos, use a smaller variant:

```bash
# Default (balanced)
dockdesk audit -w /repo --reasoning-model deepseek-r1:1.5b

# Faster (less thorough reasoning)
dockdesk audit -w /repo --reasoning-model deepseek-r1:1.5b --fast
```

## Testing on Open-Source Repos

### Recommended test targets

```bash
# Small Python (good smoke test, ~50 files)
dockdesk audit -w /tmp/httpx --max-files 30

# Medium Python (Flask, ~200 code files)
./test_on_repo.ps1 https://github.com/pallets/flask

# Large Python (FastAPI, ~400 files with docs)
./test_on_repo.ps1 https://github.com/fastapi/fastapi --max-files 100

# TypeScript (has code + README drift)  
./test_on_repo.ps1 https://github.com/sindresorhus/got

# Monorepo (Nx-style, selective audit)
dockdesk audit -w /path/to/monorepo --include "packages/core/**" --max-files 200
```

### Using the test script

```powershell
# Windows
.\test_on_repo.ps1 https://github.com/fastapi/fastapi
.\test_on_repo.ps1 C:\Projects\my-app --max-files 100 -Fast
.\test_on_repo.ps1 https://github.com/pallets/flask -Full -KeepClone
```

```bash
# Linux/macOS
./test_on_repo.sh https://github.com/fastapi/fastapi
./test_on_repo.sh /path/to/my-app --max-files 100 --fast
./test_on_repo.sh https://github.com/pallets/flask --full --keep
```

## Configuration File

For repos you audit regularly, create a `dockdesk.yml` in the repo root:

```yaml
# dockdesk.yml
model: qwen2.5-coder:3b
reasoning_model: deepseek-r1:1.5b
skip_rag: true
fast_mode: true
max_files: 200
max_file_size: 256000
workers: 4
exclude_patterns: "generated/**,vendor/**,*.min.js"
```

Then just run:

```bash
dockdesk audit -w /path/to/repo
# Config is auto-loaded from the workspace
```

## Troubleshooting

### "Ollama is not running"
```bash
ollama serve                           # Start Ollama
ollama pull qwen2.5-coder:3b          # Pull code model
ollama pull deepseek-r1:1.5b          # Pull reasoning model
```

### Slow on large repos
1. Use `--fast --max-files 100` first to verify it works.
2. Increase `--workers` if Ollama has enough VRAM.
3. Use `--include` to focus on the most important directories.
4. Use `--auto-tune` to select the right model size.

### Out of memory
- Use a smaller model: `--model qwen2.5-coder:1.5b`
- Reduce `--workers` to 1
- Reduce `--batch-size` to 3
- Increase `--max-file-size` threshold to skip large files
