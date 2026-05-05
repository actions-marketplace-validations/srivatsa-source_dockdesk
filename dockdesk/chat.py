import json
import re
from typing import Dict, Any, Optional
from rich.console import Console
from .ollama_pool import OllamaPool
from .models import DEFAULT_MODEL

console = Console()

# Quick regex matchers for common intents to avoid LLM latency when possible
_QUICK_MATCHERS = {
    r"^(?:quit|exit|q)$": {"action": "exit"},
    r"^(?:list models|models)$": {"action": "list_models"},
    r"^(?:run )?audit(?:\\s+(?:on\\s+)?(.+))?$": {"action": "audit"},
    r"^dashboard(?: stats)?$": {"action": "dashboard", "section": "summary"},
    r"^(?:open|launch|start|run) (?:react )?dashboard$": {"action": "open_react_dashboard"},
    r"^(?:init|init config)$": {"action": "init_config"},
    r"^(?:open |launch |start )?tui$": {"action": "open_tui"},
    r"^hooks?\\s+install$": {"action": "hooks", "sub_action": "install"},
    r"^hooks?\\s+uninstall$": {"action": "hooks", "sub_action": "uninstall"},
    r"^hooks?(?:\\s+status)?$": {"action": "hooks", "sub_action": "status"},
    r"^(?:install|setup)\\s+hooks?$": {"action": "hooks", "sub_action": "install"},
    r"^(?:remove|uninstall)\\s+hooks?$": {"action": "hooks", "sub_action": "uninstall"},
}

def _get_workspace_context(workspace_path: str) -> str:
    """Generate a brief topology summary of the workspace for the LLM."""
    if not workspace_path or workspace_path == "current":
        return "Unknown workspace context."
    import os
    try:
        if not os.path.exists(workspace_path):
            return "Invalid workspace path."
        
        folders = []
        files = []
        for entry in os.scandir(workspace_path):
            if entry.name.startswith("."):
                continue
            if entry.is_dir():
                folders.append(entry.name + "/")
            else:
                files.append(entry.name)
        
        summary = f"Workspace: {os.path.basename(workspace_path) or workspace_path}\n"
        summary += "Top-level contents: " + ", ".join(folders + files)
        return summary
    except Exception:
        return "Could not read workspace context."

_SYSTEM_PROMPT_TEMPLATE = """
You are the natural language intent parser for DockDesk, an AI-powered code auditing CLI.
The user will type a command in natural language. Your job is to extract their intent into a strict JSON object.

Supported actions:
1. "audit" - User wants to run an audit.
   JSON: {
     "action": "audit",
     "workspace": "<target_path_or_current>",
     "args": {
        "fast_mode": <true|false>,
        "turbo": <true|false>,
        "skip_rag": <true|false>,
        "auto_tune": <true|false>,
        "fix": <true|false>,
        "format": "<md|json|sarif>",
        "model": "<model_name>",
        "reasoning_model": "<reasoning_model_name>",
        "include": "<glob_pattern_or_file_name>"
     }
   }
   - Map fuzzy target requests (e.g., "scan the frontend", "audit auth") into the `include` field using glob patterns (e.g., "frontend/**") or filenames (e.g., "auth.py") based on the Workspace Context below. Do not put file targets in the `workspace` arg unless it's a completely different absolute path.
2. "dashboard" - User wants to view dashboard stats. They might ask for specific sections: summary, high_risk, or recent.
   JSON: {"action": "dashboard", "section": "summary" | "high_risk" | "recent"}
3. "change_workspace" - User wants to change the current workspace.
   JSON: {"action": "change_workspace", "path": "<new_path_or_browse>"}
4. "list_models" - User wants to list available models.
   JSON: {"action": "list_models"}
5. "init_config" - User wants to initialize a config file.
   JSON: {"action": "init_config"}
6. "open_react_dashboard" - User wants to open or launch the visual React dashboard.
   JSON: {"action": "open_react_dashboard"}
7. "open_tui" - User wants to open the interactive terminal dashboard (TUI).
   JSON: {"action": "open_tui"}
8. "exit" - User wants to quit or exit.
   JSON: {"action": "exit"}
9. "hooks" - User wants to manage git hooks (pre-push audit gates).
   JSON: {"action": "hooks", "sub_action": "install" | "uninstall" | "status"}
10. "unknown" - If the intent cannot be determined.
   JSON: {"action": "unknown", "message": "<a brief helpful message>"}

Workspace Context:
{workspace_context}

Rules:
- Output ONLY valid JSON. Do not include markdown code blocks or any other text.
- If the user asks "show me high risk issues", map to "dashboard" with section "high_risk".
- If the user asks "show recent audits", map to "dashboard" with section "recent".
"""

def parse_intent(user_input: str, pool: Optional[OllamaPool] = None, model: str = "gemma:2b", workspace_path: str = "") -> Dict[str, Any]:
    """Parse a natural language user string into a structured intent."""
    clean_input = user_input.strip().lower()
    
    # 1. Try quick regex matchers first for instant response (only if NO extra flags are requested)
    # We skip regex if we detect arguments like 'fast', 'model', 'using', 'fix'
    has_modifiers = any(kw in clean_input for kw in ['fast', 'turbo', 'fix', 'json', 'sarif', 'using', 'model', 'skip rag', 'auto tune'])
    if not has_modifiers:
        for pattern, intent in _QUICK_MATCHERS.items():
            match = re.match(pattern, clean_input)
            if match:
                parsed_intent = intent.copy()
                if match.groups() and match.group(1):
                    parsed_intent["workspace"] = match.group(1).strip()
                elif parsed_intent.get("action") == "audit":
                    parsed_intent["workspace"] = "current"
                return parsed_intent
            
    # 2. Fall back to LLM parsing
    if not pool:
        try:
            pool = OllamaPool([ "http://localhost:11434" ], run_health_check=False)
        except Exception:
            return {"action": "unknown", "message": "Could not connect to LLM. Try explicit commands like 'audit', 'dashboard', or 'exit'."}
            
    try:
        llm = pool.get_llm(model=model, temperature=0.0, format="json", num_predict=256)
        
        ctx_str = _get_workspace_context(workspace_path)
        system_prompt = _SYSTEM_PROMPT_TEMPLATE.replace("{workspace_context}", ctx_str)
        
        messages = [
            ("system", system_prompt),
            ("user", user_input)
        ]
        
        response = llm.invoke(messages)
        content = response.content.strip()
        
        # In case the model wrapped it in markdown
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
            
        return json.loads(content.strip())
        
    except Exception as e:
        # Fallback if LLM parsing fails
        if "audit" in clean_input:
            # Try to extract a target if specified after 'audit'
            parts = clean_input.split("audit", 1)
            target = parts[1].strip() if len(parts) > 1 else ""
            if target.startswith("on "):
                target = target[3:].strip()
            return {"action": "audit", "workspace": target if target else "current"}
        elif "dashboard" in clean_input:
            if "high" in clean_input or "risk" in clean_input:
                return {"action": "dashboard", "section": "high_risk"}
            elif "recent" in clean_input or "history" in clean_input:
                return {"action": "dashboard", "section": "recent"}
            elif "open" in clean_input or "launch" in clean_input or "start" in clean_input or "react" in clean_input:
                return {"action": "open_react_dashboard"}
            return {"action": "dashboard", "section": "summary"}
        elif "tui" in clean_input:
            return {"action": "open_tui"}
        elif "hook" in clean_input:
            if "install" in clean_input and "uninstall" not in clean_input:
                return {"action": "hooks", "sub_action": "install"}
            elif "uninstall" in clean_input or "remove" in clean_input:
                return {"action": "hooks", "sub_action": "uninstall"}
            return {"action": "hooks", "sub_action": "status"}
        elif "change" in clean_input or "cd" in clean_input or "workspace" in clean_input:
            return {"action": "change_workspace", "path": "browse"}
            
        return {"action": "unknown", "message": "Failed to parse intent"}
