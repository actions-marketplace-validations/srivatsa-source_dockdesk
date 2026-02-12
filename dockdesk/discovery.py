"""
DockDesk Discovery — Industrial-grade file discovery for monorepos.

Key improvements:
- Single os.walk() pass instead of 8+ rglob() calls  (O(n) vs O(8n))
- .gitignore support via pathspec (graceful fallback if not installed)
- Configurable include/exclude glob filters
- File-size filter (skip binaries, lock files, minified bundles)
- Lazy doc loading (paths only; content loaded on-demand)
- max_files enforcement
"""

import os
import ast
import fnmatch
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass

@dataclass
class DocumentationSource:
    path: str
    content: str
    doc_type: str
    language: str = 'text'
    line_start: int = 1
    line_end: int = 1


# ── File extension sets (single-walk matching) ──────────────────────
CODE_EXTENSIONS: Set[str] = {
    '.py', '.js', '.jsx', '.ts', '.tsx',
    '.java', '.go', '.rs', '.sh',
    '.yml', '.yaml', '.json', '.toml',
    '.css', '.html', '.sql',
    '.c', '.cpp', '.h', '.hpp',
    '.rb', '.php', '.swift', '.kt',
    '.cs', '.fs', '.ex', '.exs',
    '.scala', '.clj', '.lua', '.r',
}

DOC_EXTENSIONS: Set[str] = {'.md', '.rst', '.txt'}

SPECIAL_CODE_FILES: Set[str] = {'Dockerfile', 'Makefile', 'Jenkinsfile', 'Vagrantfile'}

# Always skip — hardcoded safety net on top of .gitignore
ALWAYS_SKIP_DIRS: Set[str] = {
    '.git', '.hg', '.svn',
    'node_modules', '__pycache__', '.tox',
    'venv', '.venv', 'env', '.env',
    '.dockdesk_cache', '.chroma_db',
    'dist', 'build', '.next', '.nuxt',
    'coverage', '.nyc_output',
    '.terraform', '.serverless',
    'legacy',
}

DEFAULT_MAX_FILE_SIZE = 500 * 1024  # 500 KB


def _load_gitignore_matcher(root: str):
    """Load .gitignore / .dockerignore / .dockdeskignore patterns."""
    try:
        import pathspec
    except ImportError:
        return None

    patterns = []
    for ignore_file in ['.gitignore', '.dockerignore', '.dockdeskignore']:
        ignore_path = os.path.join(root, ignore_file)
        if os.path.isfile(ignore_path):
            try:
                with open(ignore_path, 'r', encoding='utf-8') as f:
                    patterns.extend(f.read().splitlines())
            except Exception:
                continue
    if not patterns:
        return None
    try:
        return pathspec.PathSpec.from_lines('gitwildmatch', patterns)
    except Exception:
        return None


class Discovery:
    """Fast, scalable file discovery for monorepos (100K+ files).

    Single os.walk() pass with .gitignore support, size/count limits,
    and configurable include/exclude filters.
    """

    # Legacy API compatibility
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

    def __init__(
        self,
        root_dir: str = ".",
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
        max_file_size: int = DEFAULT_MAX_FILE_SIZE,
        max_files: int = 0,
        respect_gitignore: bool = True,
    ):
        self.root_dir = Path(root_dir).resolve()
        self.root_str = str(self.root_dir)
        self.include_patterns = include_patterns or []
        self.exclude_patterns = exclude_patterns or []
        self.max_file_size = max_file_size
        self.max_files = max_files
        self.respect_gitignore = respect_gitignore
        self._gitignore = _load_gitignore_matcher(self.root_str) if respect_gitignore else None
        self._exclude_compiled = [p for p in self.exclude_patterns if p]

    def _should_skip_dir(self, dir_name: str, rel_path: str) -> bool:
        """Check if a directory should be pruned from the walk."""
        if dir_name.startswith('.') and dir_name not in ('.github',):
            return True
        if dir_name in ALWAYS_SKIP_DIRS:
            return True
        if self._gitignore and self._gitignore.match_file(rel_path + '/'):
            return True
        for pat in self._exclude_compiled:
            if fnmatch.fnmatch(rel_path, pat) or fnmatch.fnmatch(dir_name, pat):
                return True
        return False

    def _classify_file(self, rel_path: str, file_name: str, file_size: int) -> Tuple[bool, bool]:
        """Returns (is_code, is_doc)."""
        if file_size > self.max_file_size:
            return False, False
        if self._gitignore and self._gitignore.match_file(rel_path):
            return False, False
        for pat in self._exclude_compiled:
            if fnmatch.fnmatch(rel_path, pat) or fnmatch.fnmatch(file_name, pat):
                return False, False
        if self.include_patterns:
            if not any(fnmatch.fnmatch(rel_path, p) or fnmatch.fnmatch(file_name, p)
                       for p in self.include_patterns):
                return False, False
        ext = os.path.splitext(file_name)[1].lower()
        is_code = ext in CODE_EXTENSIONS or file_name in SPECIAL_CODE_FILES
        is_doc = ext in DOC_EXTENSIONS or file_name == 'LICENSE'
        return is_code, is_doc

    def _single_walk(self) -> Tuple[List[str], List[str]]:
        """Single os.walk() pass → (code_files, doc_paths). O(n)."""
        code_files: List[str] = []
        doc_paths: List[str] = []
        code_limit = self.max_files if self.max_files > 0 else float('inf')

        for dirpath, dirnames, filenames in os.walk(self.root_str):
            rel_dir = os.path.relpath(dirpath, self.root_str)
            if rel_dir == '.':
                rel_dir = ''

            # Prune dirs in-place
            dirnames[:] = [
                d for d in dirnames
                if not self._should_skip_dir(d, os.path.join(rel_dir, d) if rel_dir else d)
            ]

            for fname in filenames:
                if len(code_files) >= code_limit:
                    break
                rel_path = os.path.join(rel_dir, fname) if rel_dir else fname
                full_path = os.path.join(dirpath, fname)
                try:
                    fsize = os.path.getsize(full_path)
                except OSError:
                    continue
                is_code, is_doc = self._classify_file(rel_path, fname, fsize)
                if is_code:
                    code_files.append(full_path)
                if is_doc:
                    doc_paths.append(full_path)

            if len(code_files) >= code_limit:
                break

        return code_files, doc_paths

    # ── Legacy-compatible public API ──────────────────────────────────

    def find_code_files(self) -> List[str]:
        """Find all code files. Single-pass, filtered."""
        code_files, _ = self._single_walk()
        return sorted(code_files)

    def find_docs(self) -> List[DocumentationSource]:
        """Find doc files and load content (backward compatible)."""
        _, doc_paths = self._single_walk()
        sources = []
        for fpath in doc_paths:
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    content = f.read()
                sources.append(DocumentationSource(
                    path=fpath,
                    content=content,
                    doc_type='file',
                    language='markdown' if fpath.endswith('.md') else 'text',
                ))
            except Exception:
                continue
        return sources

    def find_docs_lazy(self) -> List[str]:
        """Find doc file paths WITHOUT loading content. Use load_doc_content() on-demand."""
        _, doc_paths = self._single_walk()
        return sorted(doc_paths)

    @staticmethod
    def load_doc_content(doc_path: str, max_size: int = 50000) -> Optional[DocumentationSource]:
        """Load a single doc file's content on-demand, with size cap."""
        try:
            fsize = os.path.getsize(doc_path)
            if fsize > max_size:
                return None
            with open(doc_path, 'r', encoding='utf-8') as f:
                content = f.read(max_size)
            return DocumentationSource(
                path=doc_path,
                content=content,
                doc_type='file',
                language='markdown' if doc_path.endswith('.md') else 'text',
            )
        except Exception:
            return None

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
        except Exception:
            return []

    def summary(self) -> dict:
        """Discovery statistics."""
        code_files, doc_paths = self._single_walk()
        return {
            "code_files": len(code_files),
            "doc_files": len(doc_paths),
            "root": self.root_str,
            "gitignore_active": self._gitignore is not None,
            "max_files": self.max_files,
            "max_file_size": self.max_file_size,
        }

