import os
import ast
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class DocumentationSource:
    path: str
    content: str
    doc_type: str
    language: str = 'text'
    line_start: int = 1
    line_end: int = 1

class Discovery:
    CODE_PATTERNS = {
        'python': ['**/*.py'],
        'javascript': ['**/*.js', '**/*.jsx', '**/*.ts', '**/*.tsx'],
        'java': ['**/*.java'],
        'go': ['**/*.go'],
        'rust': ['**/*.rs'],
        'docker': ['Dockerfile*'],
        'shell': ['**/*.sh']
    }

    DOC_PATTERNS = ['**/*.md', '**/*.rst', '**/*.txt', '**/LICENSE']

    def __init__(self, root_dir: str = "."):
        self.root_dir = Path(root_dir).resolve()

    def _glob(self, patterns: List[str]) -> List[Path]:
        files = []
        for pattern in patterns:
            try:
                # Handle recursive globbing manually if needed or rely on rglob
                if "**" in pattern:
                    parts = pattern.split("**")
                    ext = parts[1] if len(parts) > 1 else "*"
                    found = list(self.root_dir.rglob(ext.lstrip("/")))
                else:
                    found = list(self.root_dir.glob(pattern))
                
                # Filter out hidden files and legacy folder
                files.extend([
                    f for f in found 
                    if f.is_file() 
                    and not any(p.startswith('.') for p in f.parts) 
                    and 'legacy' not in f.parts
                    and 'node_modules' not in f.parts
                    and 'venv' not in f.parts
                ])
            except Exception:
                continue
        return sorted(list(set(files)))

    def find_code_files(self) -> List[str]:
        patterns = [p for sublist in self.CODE_PATTERNS.values() for p in sublist]
        return [str(f) for f in self._glob(patterns)]

    def find_docs(self) -> List[DocumentationSource]:
        doc_files = self._glob(self.DOC_PATTERNS)
        sources = []
        for f in doc_files:
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    content = file.read()
                    sources.append(DocumentationSource(
                        path=str(f),
                        content=content,
                        doc_type='file',
                        language='markdown' if f.suffix == '.md' else 'text'
                    ))
            except:
                continue
        return sources

    def extract_docstrings(self, file_path: str) -> List[DocumentationSource]:
        """Extracts docstrings from Python files."""
        if not file_path.endswith('.py'):
            return []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            docs = []
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    docstring = ast.get_docstring(node)
                    if docstring:
                        name = getattr(node, 'name', 'module')
                        line = getattr(node, 'lineno', 1)
                        docs.append(DocumentationSource(
                            path=f"{file_path}::{name}",
                            content=docstring,
                            doc_type='docstring',
                            language='python',
                            line_start=line,
                            line_end=line + docstring.count('\n')
                        ))
            return docs
        except:
            return []
