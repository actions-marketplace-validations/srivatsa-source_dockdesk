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
    r"^(?:run )?audit$": {"action": "audit", "workspace": "current"},
    r"^dashboard(?: stats)?$": {"action": "dashboard", "section": "summary"},
    r"^(?:open|launch|start|run) (?:react )?dashboard$": {"action": "open_react_dashboard"},
    r"^(?:init|init config)$": {"action": "init_config"},
    r"^(?:open |launch |start )?tui$": {"action": "open_tui"},
}

_SYSTEM_PROMPT = """
You are the natural language intent parser for DockDesk, an AI-powered code auditing CLI.
The user will type a command in natural language. Your job is to extract their intent into a strict JSON object.

Supported actions:
1. "audit" - User wants to run an audit on the current or a specific workspace.
   JSON: {"action": "audit", "workspace": "current" or "<path>"}
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
9. "unknown" - If the intent cannot be determined.
   JSON: {"action": "unknown", "message": "<a brief helpful message>"}

Rules:
- Output ONLY valid JSON. Do not include markdown code blocks or any other text.
- If the user asks "show me high risk issues", map to "dashboard" with section "high_risk".
- If the user asks "show recent audits", map to "dashboard" with section "recent".
"""

def parse_intent(user_input: str, pool: Optional[OllamaPool] = None, model: str = DEFAULT_MODEL) -> Dict[str, Any]:
    """Parse a natural language user string into a structured intent."""
    clean_input = user_input.strip().lower()
    
    # 1. Try quick regex matchers first for instant response
    for pattern, intent in _QUICK_MATCHERS.items():
        if re.match(pattern, clean_input):
            return intent
            
    # 2. Fall back to LLM parsing
    if not pool:
        try:
            pool = OllamaPool([ "http://localhost:11434" ], run_health_check=False)
        except Exception:
            return {"action": "unknown", "message": "Could not connect to LLM. Try explicit commands like 'audit', 'dashboard', or 'exit'."}
            
    try:
        llm = pool.get_llm(model=model, temperature=0.0, format="json", num_predict=128)
        
        messages = [
            ("system", _SYSTEM_PROMPT),
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
            return {"action": "audit", "workspace": "current"}
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
        elif "change" in clean_input or "cd" in clean_input or "workspace" in clean_input:
            return {"action": "change_workspace", "path": "browse"}
            
        return {"action": "unknown", "message": "Failed to parse intent"}
