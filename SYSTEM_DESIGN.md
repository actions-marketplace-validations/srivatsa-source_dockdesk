# System Design: The Neural Loop

The "Neural Loop" is the core cognitive architecture of the DockDesk Integrity Agent. It converts unstructured natural language validation into a deterministic pipeline suitable for CI/CD environments.

## Architecture

![Neural Loop Diagram](https://mermaid.ink/img/pako:eNpVkMtuwjAQRX_FclYt8QNdcJEqWinsqqtKfIwmHhI78kzaIP59nZQWdTP3XD1zR5hYCRrh8L61VfvCKeO9lqba2_u7s8_3M_v6eGeva_t8t4_P9_uH_f3D_n5n39_v7Pvt3b6_2_f7u31_t-_3d_v-bt_f7fv93b7f3-37_d2-39_t-_3dvt_f7fv93b7f3-37_d2-39_t-_3dvt_f7fv93b7f3-37_d2-39_t-_3dvt_f7fv93b7f3-37_d2-39_t-_3dvt_f7fv)

### 1. Hash (Merklization)
**Objective:** Deterministic Change Detection.
- The system reads the target code usage (`auth.py`) and calculates a SHA-256 hash.
- This serves as a "Merkle Leaf" to verify if the code has actually changed before invoking the expensive prompt chain.
- **Fail-Fast:** If the hash matches the previous known good state, the audit is skipped (optimization).

### 2. Prompt (Chain-of-Thought)
**Objective:** Contextual Loading.
- **Input:** Raw source code (`auth.py`) + Documentation (`README.md`).
- **System Prompt:** Instructs the LLM to act as a "Lead Security Auditor".
- **Strategy:** "EXTRACT -> COMPARE" thought process. The model isolates logic requirements from code and claims from docs, then compares them side-by-side.
- **Strict Mode:** Temperature is set to `0.1` to reduce creative hullication.

### 3. Parse (Heuristic Regex)
**Objective:** Output Sanitation.
- Small models (3B) often output "conversational garbage" (e.g., "Sure, here is the JSON...").
- The semantic parser strips markdown fences and uses regex fallbacks to extract the JSON payload even if the JSON syntax is slightly broken (e.g., unescaped newlines).
- **Self-Healing:** If standard `json.loads` fails, the `clean_json` method scrapes specific keys (`status`, `fix`) using regex patterns.

### 4. Diff (Actionable Feedback)
**Objective:** Human-in-the-Loop Fix.
- **CI Mode:** 
    - Exits with `1` on failure.
    - Generates `audit_report.md` for GitHub PR comments.
- **Interactive Mode:**
    - Displays `risk` level in terminal.
    - Extracts the `fix` payload (rewritten README content).
    - Prompts user to apply the fix immediately.
