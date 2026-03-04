"""
DockDesk N-ary Merkle Tree with SQLite Indexing

This module implements an efficient file system hashing mechanism for large repositories.
It uses:
  1. SQLite-backed persistent index (mtime/size check) to avoid re-hashing unchanged files.
  2. Parallel I/O via ThreadPoolExecutor for new/modified files.
  3. Simple N-ary Merkle Tree structure (directory hash = SHA-256 of sorted children).

Complexity:
  - Full build (cold): O(N) where N = total files (parallelized I/O).
  - Incremental build (warm): O(k) where k = changed files (stat check is fast).
  - Diff: O(k) tree traversal.
"""

import os
import hashlib
import sqlite3
import concurrent.futures
from enum import Enum
from typing import Dict, List, Optional, Set, Union
from dataclasses import dataclass, field

# Try to use xxhash for speed, fallback to sha256
try:
    import xxhash
    HAS_XXHASH = True
except ImportError:
    HAS_XXHASH = False


class NodeType(str, Enum):
    FILE = "file"
    DIR = "dir"


IGNORE_DIRS = {
    ".git", ".venv", "venv", "__pycache__", "node_modules",
    "legacy", ".idea", ".vscode", "dist", "build", "target",
    ".mypy_cache", ".pytest_cache", ".tox", "egg-info", ".dockdesk_cache.db", ".dockdesk_merkle.db"
}


def _should_skip(entry: str) -> bool:
    return entry in IGNORE_DIRS or entry.startswith(".")


@dataclass
class FileMeta:
    path: str
    mtime: float
    size: int
    hash_val: str


@dataclass
class MerkleNode:
    name: str
    type: NodeType
    path: str
    hash: str = ""
    # Only for directories:
    children: Dict[str, "MerkleNode"] = field(default_factory=dict)
    # Compatibility with old binary tree API (deprecated but kept to avoid immediate breakage)
    file_tree: Optional["MerkleNode"] = None 

    def to_dict(self) -> dict:
        d = {
            "name": self.name,
            "type": self.type.value,
            "path": self.path,
            "hash": self.hash,
        }
        if self.children:
            d["children"] = {k: v.to_dict() for k, v in self.children.items()}
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "MerkleNode":
        if not isinstance(data, dict):
            return None
        node = cls(data.get("name", ""), NodeType(data.get("type", "file")), data.get("path", ""), data.get("hash", ""))
        for child_name, child_data in data.get("children", {}).items():
            child = cls.from_dict(child_data)
            if child:
                node.children[child_name] = child
        return node


# -- SQLite Index Manager ---------------------------------------------------

class IndexManager:
    """
    Manages a persistent index of file metadata (mtime, size, hash).
    Uses SQLite for robust, cross-platform storage.
    """
    def __init__(self, workspace: str, db_name: str = ".dockdesk_merkle.db"):
        self.db_path = os.path.join(workspace, db_name)
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _init_db(self):
        try:
            with self._get_conn() as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS file_index (
                        path TEXT PRIMARY KEY,
                        mtime REAL,
                        size INTEGER,
                        hash TEXT
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_mtime ON file_index(mtime)")
        except sqlite3.OperationalError:
            pass

    def get_all_meta(self) -> Dict[str, FileMeta]:
        """Load entire index into memory (path -> FileMeta)."""
        meta_map = {}
        try:
            with self._get_conn() as conn:
                cursor = conn.execute("SELECT path, mtime, size, hash FROM file_index")
                for row in cursor:
                    meta_map[row[0]] = FileMeta(row[0], row[1], row[2], row[3])
        except (sqlite3.OperationalError, sqlite3.DatabaseError):
            pass
        return meta_map

    def update_batch(self, metas: List[FileMeta]):
        """Update multiple file entries in a single transaction."""
        if not metas:
            return
        try:
            with self._get_conn() as conn:
                conn.executemany(
                    "INSERT OR REPLACE INTO file_index (path, mtime, size, hash) VALUES (?, ?, ?, ?)",
                    [(m.path, m.mtime, m.size, m.hash_val) for m in metas]
                )
        except (sqlite3.OperationalError, sqlite3.DatabaseError):
            pass

    def purge_missing(self, current_paths: Set[str]):
        """Remove entries for files that no longer exist."""
        try:
            with self._get_conn() as conn:
                db_paths = set(row[0] for row in conn.execute("SELECT path FROM file_index"))
                to_remove = db_paths - current_paths
                if to_remove:
                    conn.executemany("DELETE FROM file_index WHERE path = ?", [(p,) for p in to_remove])
        except (sqlite3.OperationalError, sqlite3.DatabaseError):
            pass


# -- Hashing Logic ----------------------------------------------------------

def compute_file_hash(filepath: str) -> str:
    """Compute hash of a file using xxhash (fast) or sha256 (fallback)."""
    if HAS_XXHASH:
        hasher = xxhash.xxh64()
    else:
        hasher = hashlib.sha256()

    try:
        # Use 64KB chunks for optimal I/O on modern drives
        with open(filepath, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()
    except (PermissionError, FileNotFoundError, OSError):
        return ""


def _process_file(args):
    """Worker function for parallel hashing."""
    filepath, mtime, size = args
    new_hash = compute_file_hash(filepath)
    return FileMeta(filepath, mtime, size, new_hash)


# -- Tree Construction ------------------------------------------------------

def build_merkle_tree(workspace: str, index_manager: Optional[IndexManager] = None) -> MerkleNode:
    """
    Build N-ary Merkle Tree for workspace using parallel I/O and persistent caching.
    """
    workspace = os.path.abspath(workspace)
    
    # 1. Initialize Index
    if index_manager is None:
        try:
            index_manager = IndexManager(workspace)
        except Exception:
            index_manager = None

    cached_meta = index_manager.get_all_meta() if index_manager else {}
    
    # 2. Scan Files System
    current_files: Dict[str, os.stat_result] = {}
    all_paths = set()

    for root, dirs, files in os.walk(workspace, topdown=True):
        dirs[:] = [d for d in dirs if not _should_skip(d)]
        
        for name in files:
            if _should_skip(name):
                continue
            path = os.path.join(root, name)
            try:
                stat = os.stat(path)
                current_files[path] = stat
                all_paths.add(path)
            except OSError:
                continue

    # 3. Identify Dirty Files
    dirty_files = [] # List[(path, mtime, size)]
    valid_metas: Dict[str, FileMeta] = {} # path -> FileMeta

    for path, stat in current_files.items():
        meta = cached_meta.get(path)
        if meta and meta.mtime == stat.st_mtime and meta.size == stat.st_size:
            valid_metas[path] = meta
        else:
            dirty_files.append((path, stat.st_mtime, stat.st_size))

    # 4. Process Dirty Files in Parallel
    if dirty_files:
        max_workers = min(32, (os.cpu_count() or 1) + 4)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = executor.map(_process_file, dirty_files)
            
        new_metas = list(results)
        for meta in new_metas:
            valid_metas[meta.path] = meta
        
        if index_manager:
            index_manager.update_batch(new_metas)

    if index_manager:
        index_manager.purge_missing(all_paths)

    # 5. Build Tree Structure (Recursive)
    return _build_tree_recursive(workspace, valid_metas)


def _build_tree_recursive(current_path: str, valid_metas: Dict[str, FileMeta]) -> MerkleNode:
    """Recursively build the tree structure from directory scan."""
    name = os.path.basename(current_path.rstrip(os.sep)) or current_path
    node = MerkleNode(name, NodeType.DIR, current_path)
    
    try:
        entries = sorted(os.listdir(current_path))
    except OSError:
        entries = []
        
    child_hashes = []
    
    for entry in entries:
        if _should_skip(entry):
            continue
            
        full_path = os.path.join(current_path, entry)
        
        if os.path.isdir(full_path):
            child_node = _build_tree_recursive(full_path, valid_metas)
            node.children[entry] = child_node
            child_hashes.append(child_node.hash)
            
        elif os.path.isfile(full_path):
            if full_path in valid_metas:
                meta = valid_metas[full_path]
                file_node = MerkleNode(entry, NodeType.FILE, full_path, meta.hash_val)
                node.children[entry] = file_node
                child_hashes.append(meta.hash_val)
    
    if child_hashes:
        # Sorting is implicit because entries was sorted
        node.hash = hashlib.sha256("".join(child_hashes).encode()).hexdigest()
    
    return node


# -- Tree Diff --------------------------------------------------------------

def get_merkle_diff(
    old_node: Union[MerkleNode, dict, None], new_node: MerkleNode
) -> Dict[str, List[str]]:
    """
    Compute diff between old and new Merkle trees.
    Returns dict with keys: added, removed, modified.
    """
    if isinstance(old_node, dict):
        try:
            old_node = MerkleNode.from_dict(old_node)
        except Exception:
            old_node = None

    diffs = {"added": [], "removed": [], "modified": []}
    
    if not isinstance(old_node, MerkleNode):
        _collect_all_files(new_node, diffs["added"])
        return diffs

    if old_node.hash == new_node.hash:
        return diffs

    _compare_nodes(old_node, new_node, diffs)
    return diffs


def _compare_nodes(old: MerkleNode, new: MerkleNode, diffs: Dict[str, List[str]]):
    """Recursively compare two nodes."""
    old_keys = set(old.children.keys())
    new_keys = set(new.children.keys())
    
    for key in new_keys - old_keys:
        _collect_all_files(new.children[key], diffs["added"])
        
    for key in old_keys - new_keys:
        _collect_all_files(old.children[key], diffs["removed"])
        
    for key in old_keys & new_keys:
        child_old = old.children[key]
        child_new = new.children[key]
        
        if child_old.hash != child_new.hash:
            if child_new.type == NodeType.FILE:
                diffs["modified"].append(child_new.path)
            else:
                _compare_nodes(child_old, child_new, diffs)


def _collect_all_files(node: MerkleNode, acc: List[str]):
    """Recursively collect all file paths."""
    if node.type == NodeType.FILE:
        acc.append(node.path)
    else:
        for child in node.children.values():
            _collect_all_files(child, acc)

