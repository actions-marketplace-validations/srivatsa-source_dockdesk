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
        Generates a Mermaid graph showing affected files and their risk levels.
        """
        graph = ["graph TD"]
        graph.append("    style START fill:#f9f,stroke:#333,stroke-width:2px")
        graph.append("    START[Audit Start] --> DIFF{Changes Detected?}")
        
        if not changes:
            graph.append("    DIFF -- No --> END[Pass]")
            graph.append("    style END fill:#9f9,stroke:#333,stroke-width:4px")
            return "\n".join(graph)

        graph.append("    DIFF -- Yes --> NODES")
        
        for file in changes:
            clean_name = file.replace(".", "_").replace("/", "_").replace("\\", "_")
            risk = risk_map.get(file, "UNKNOWN")
            
            color = "#eee"
            if risk == "HIGH": color = "#ff9999"
            elif risk == "MEDIUM": color = "#ffff99"
            elif risk == "LOW": color = "#99ff99"
            
            graph.append(f"    NODES --> {clean_name}[{file}]")
            graph.append(f"    style {clean_name} fill:{color},stroke:#333")
            
        return "```mermaid\n" + "\n".join(graph) + "\n```"

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
