# System Design: The Neural Loop

The "Neural Loop" is the core cognitive architecture of the DockDesk Integrity Agent. It converts unstructured natural language validation into a deterministic pipeline suitable for CI/CD environments.

## Architecture

```mermaid
flowchart TD
    subgraph INPUT["📂 Input"]
        LOCAL["Local path"]
        GITURL["Git URL"]
    end

    subgraph PIPELINE["⚙️ Audit Pipeline"]
        direction TB
        DISCOVER["🔍 Discovery<br/><i>files · .gitignore · include/exclude</i>"]
        INTEGRITY["🔐 Integrity & Cache<br/><i>Git diff / SQLite Persistence</i>"]
        RAG["📚 RAG Context<br/><i>AST-aware splitting · ChromaDB</i>"]
        CODE["🧠 Code Analysis<br/><i>Qwen Coder 7B</i>"]
        REASON["💡 Reasoning<br/><i>DeepSeek-R1 1.5B</i>"]
        REPORT["📊 Reporting"]
        DISCOVER --> INTEGRITY --> RAG --> CODE --> REASON --> REPORT
    end

    subgraph RULES["📏 Custom Rules"]
        CLI_RULES["--rules flag"]
        CONFIG_RULES["dockdesk.yml"]
    end

    subgraph OLLAMA["🦙 Ollama"]
        OL_LOCAL["localhost:11434"]
        OL_POOL["Distributed pool"]
    end

    subgraph OUTPUT["📤 Output"]
        MD["Markdown"]
        SARIF["SARIF"]
        JSON["JSON"]
        FIX["Auto-Fixes"]
        DASH["Dashboard"]
    end

    LOCAL & GITURL --> DISCOVER
    CLI_RULES & CONFIG_RULES -.->|inject| CODE
    CODE & REASON <-->|inference| OLLAMA
    REPORT --> OUTPUT
```

### 1. Discovery, Integrity & Cache (Steps 1-2)
**Objective:** Deterministic Change Detection and State Persistence.
- Discovery scans the workspace for code files and documentation, respecting `.gitignore` and include/exclude globs.
- Integrity primarily uses **Differential Git-Diff** to massively improve audit speeds by exclusively targeting modified files.
- Untracked files are included via `git ls-files --others --exclude-standard`.
- **SQLite Persistence:** Audit state is permanently cached in an SQLite database, allowing for resilient re-runs and immediate fail-fast skipping of unchanged files.

### 2. RAG Context (Step 3)
**Objective:** Contextual Loading via AST-Aware Splitting.
- Documentation and code are ingested into a ChromaDB vector store.
- **AST-aware splitters** for 20+ languages (Python, JS, Java, Go, Rust, etc.) preserve semantic boundaries.
- Falls back to recursive character splitting for unsupported file types.
- Skippable via `--skip-rag` for faster audits.

### 3. Code Analysis (Step 4)
**Objective:** Semantic Drift Detection.
- **Code Agent:** Qwen Coder 7B analyzes each file against its documentation.
- **Custom Rules:** User-defined rules from `--rules` flag or `dockdesk.yml` are injected into the system prompt.
- Supports individual and batched analysis modes.
- Results are cached in SQLite for incremental re-runs.
- **Strict Mode:** Temperature is set to `0.1` to reduce creative hallucination.

### 4. Reasoning (Step 5)
**Objective:** Risk Assessment & Push Safety.
- **Reasoning Agent:** DeepSeek-R1 1.5B reviews code analysis results and assigns risk levels (HIGH/MEDIUM/LOW).
- PASS files are skipped (no reasoning needed).
- Fast mode (`--fast`) skips reasoning for low-signal files.
- Determines `safe_to_push` verdict for each file.

### 5. Reporting (Step 6)
**Objective:** Human-in-the-Loop Feedback.
- **Formats:** Markdown, JSON, SARIF (for IDE/Code Scanning integration).
- **CI Mode:** Exits with code 1 on risk threshold breach.
- **Auto-Fix:** Optional `--fix` flag applies documentation corrections.
- **Dashboard:** Auto-exports `dashboard_data.json` for the React dashboard. Now features a Settings Panel, Model Pulling, and Sequential Knowledge Graph.
- **Changelog:** Appends to `audit_history.jsonl` for trend tracking.
