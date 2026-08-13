import hashlib
import json
import ast
import os
from pathlib import Path
from typing import Dict, List, Any
from rich.console import Console

console = Console()

CACHE_FILE = ".audit_cache.json"

class AuditCache:
    def __init__(self):
        self.cache = self._load_cache()

    def _load_cache(self) -> Dict[str, str]:
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_cache(self):
        with open(CACHE_FILE, 'w') as f:
            json.dump(self.cache, f, indent=2)

    def get_hash(self, file_path: str) -> str:
        return self.cache.get(file_path)

    def update_hash(self, file_path: str, file_hash: str):
        self.cache[file_path] = file_hash

    @staticmethod
    def calculate_file_hash(content: str) -> str:
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

class Visualizer:
    @staticmethod
    def generate_mermaid_graph(changes: List[str], risk_map: Dict[str, str]) -> str:
        """
        Generates a Mermaid pipeline flowchart showing the audit flow
        with per-file risk indicators.
        """
        lines: List[str] = ["flowchart TD"]

        # ── Pipeline spine ──
        lines.append("    DISCOVER[\"Discovery\"] --> INTEGRITY[\"Integrity Check\"]")
        lines.append("    INTEGRITY --> RAG[\"RAG Context\"]")
        lines.append("    RAG --> CODE[\"Code Analysis<br/><i>Qwen Coder</i>\"]")
        lines.append("    CODE --> REASON[\"Reasoning<br/><i>DeepSeek-R1</i>\"]")
        lines.append("    REASON --> REPORT[\"Report\"]")

        # ── Pipeline node styles ──
        lines.append("    style DISCOVER fill:#0277bd,stroke:#01579b,color:#fff,rx:6")
        lines.append("    style INTEGRITY fill:#0277bd,stroke:#01579b,color:#fff,rx:6")
        lines.append("    style RAG fill:#0277bd,stroke:#01579b,color:#fff,rx:6")
        lines.append("    style CODE fill:#1565c0,stroke:#0d47a1,color:#fff,rx:6")
        lines.append("    style REASON fill:#1565c0,stroke:#0d47a1,color:#fff,rx:6")
        lines.append("    style REPORT fill:#00838f,stroke:#006064,color:#fff,rx:6")

        if not changes:
            lines.append("    INTEGRITY -- No changes --> DONE[\"Clean\"]")
            lines.append("    style DONE fill:#2e7d32,stroke:#1b5e20,color:#fff,rx:8")
            return "```mermaid\n" + "\n".join(lines) + "\n```"

        # ── File risk nodes branching from REPORT ──
        risk_colors = {
            "HIGH": ("#c62828", "#b71c1c"),   # red
            "MEDIUM": ("#f57f17", "#e65100"),  # amber
            "LOW": ("#2e7d32", "#1b5e20"),     # green
        }
        for idx, file in enumerate(changes):
            node_id = f"F{idx}"
            risk = risk_map.get(file, "UNKNOWN")
            # Short display name
            short = os.path.basename(file)
            icon = {"HIGH": "HIGH", "MEDIUM": "MEDIUM", "LOW": "LOW"}.get(risk, "UNKNOWN")
            lines.append(f"    REPORT --> {node_id}[\"{icon} {short}<br/>{risk}\"]")
            fill, stroke = risk_colors.get(risk, ("#616161", "#424242"))
            lines.append(f"    style {node_id} fill:{fill},stroke:{stroke},color:#fff,rx:6")

        return "```mermaid\n" + "\n".join(lines) + "\n```"

class Guardrails:
    @staticmethod
    def validate_python_syntax(code: str) -> bool:
        """
        Validates if the provided code string is valid Python syntax.
        """
        try:
            ast.parse(code)
            return True
        except SyntaxError:
            return False

    @staticmethod
    def sanitize_fix(fix_text: str) -> str:
        """
        Extracts code from markdown blocks if present.
        """
        if "```python" in fix_text:
            start = fix_text.find("```python") + 9
            end = fix_text.find("```", start)
            return fix_text[start:end].strip()
        elif "```" in fix_text:
            start = fix_text.find("```") + 3
            end = fix_text.find("```", start)
            return fix_text[start:end].strip()
        return fix_text
