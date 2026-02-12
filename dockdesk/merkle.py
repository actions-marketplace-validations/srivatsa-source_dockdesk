"""
DockDesk Hybrid Binary Merkle Tree

Directory-level N-ary tree for subtree pruning (unchanged dirs skipped in O(1)).
Within each directory, files are arranged in a balanced binary Merkle tree
for O(k log n) change detection — critical for industrial monorepos.

Complexity:
  - Full build: O(n) where n = total files
  - Diff: O(k * log m) where k = changed dirs, m = max files per dir
  - Unchanged directory: O(1) skip via root hash comparison
"""

import os
import hashlib
from enum import Enum
from typing import Dict, List, Optional, Union


class NodeType(str, Enum):
    FILE = "file"
    DIR = "dir"


# ── Binary Merkle Node (file-level, within a single directory) ──────────────

class BinaryMerkleNode:
    """
    A node in a balanced binary Merkle tree of files within a directory.
    Leaves hold a file path + its content hash.
    Internal nodes hold SHA-256(left.hash || right.hash).
    """
    __slots__ = ("hash", "leaf_path", "left", "right")

    def __init__(
        self,
        hash_val: str = "",
        leaf_path: str = "",
        left: Optional["BinaryMerkleNode"] = None,
        right: Optional["BinaryMerkleNode"] = None,
    ):
        self.hash = hash_val
        self.leaf_path = leaf_path   # non-empty only for leaves
        self.left = left
        self.right = right

    @property
    def is_leaf(self) -> bool:
        return self.left is None and self.right is None

    def to_dict(self) -> dict:
        d: dict = {"hash": self.hash}
        if self.leaf_path:
            d["leaf_path"] = self.leaf_path
        if self.left:
            d["left"] = self.left.to_dict()
        if self.right:
            d["right"] = self.right.to_dict()
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "BinaryMerkleNode":
        node = cls(hash_val=data.get("hash", ""), leaf_path=data.get("leaf_path", ""))
        if "left" in data:
            node.left = cls.from_dict(data["left"])
        if "right" in data:
            node.right = cls.from_dict(data["right"])
        return node


def _build_binary_tree(leaves: List[BinaryMerkleNode]) -> Optional[BinaryMerkleNode]:
    """Build a balanced binary Merkle tree from sorted leaf nodes. O(n)."""
    if not leaves:
        return None
    if len(leaves) == 1:
        return leaves[0]

    mid = len(leaves) // 2
    left = _build_binary_tree(leaves[:mid])
    right = _build_binary_tree(leaves[mid:])

    combined = ""
    if left:
        combined += left.hash
    if right:
        combined += right.hash

    return BinaryMerkleNode(
        hash_val=hashlib.sha256(combined.encode()).hexdigest(),
        left=left,
        right=right,
    )


def _diff_binary_trees(
    old: Optional[BinaryMerkleNode],
    new: Optional[BinaryMerkleNode],
    modified: List[str],
    added: List[str],
    removed: List[str],
) -> None:
    """
    O(k log n) diff between two binary Merkle trees.
    Skips entire subtrees when hashes match.
    """
    if old is None and new is None:
        return

    if old is None and new is not None:
        _collect_binary_leaves(new, added)
        return

    if old is not None and new is None:
        _collect_binary_leaves(old, removed)
        return

    # Hash match → entire subtree unchanged, skip
    if old.hash == new.hash:
        return

    # Both are leaves
    if old.is_leaf and new.is_leaf:
        if old.leaf_path == new.leaf_path:
            modified.append(new.leaf_path)
        else:
            removed.append(old.leaf_path)
            added.append(new.leaf_path)
        return

    # Structural mismatch (one leaf, one internal)
    if old.is_leaf != new.is_leaf:
        _collect_binary_leaves(old, removed)
        _collect_binary_leaves(new, added)
        return

    # Both internal → recurse left and right
    _diff_binary_trees(old.left, new.left, modified, added, removed)
    _diff_binary_trees(old.right, new.right, modified, added, removed)


def _collect_binary_leaves(node: Optional[BinaryMerkleNode], acc: List[str]) -> None:
    """Collect all leaf paths from a binary tree."""
    if node is None:
        return
    if node.is_leaf:
        if node.leaf_path:
            acc.append(node.leaf_path)
        return
    _collect_binary_leaves(node.left, acc)
    _collect_binary_leaves(node.right, acc)


# ── Directory-level N-ary Merkle Node ───────────────────────────────────────

IGNORE_DIRS = {
    '.git', '.venv', 'venv', '__pycache__', 'node_modules',
    'legacy', '.idea', '.vscode', 'dist', 'build', 'target',
    '.mypy_cache', '.pytest_cache', '.tox', 'egg-info',
}


def _should_skip(entry: str) -> bool:
    return entry in IGNORE_DIRS or entry.startswith('.')


class MerkleNode:
    """
    Hybrid Merkle tree node.
    
    Directories store:
      - children: Dict[str, MerkleNode] — subdirectory children (N-ary)
      - file_tree: BinaryMerkleNode — balanced binary tree of files in THIS dir
    
    The directory hash = SHA-256(sorted subdir hashes + file_tree root hash).
    """

    def __init__(self, name: str, node_type: NodeType, path: str):
        self.name = name
        self.type = node_type
        self.path = path
        self.hash: str = ""
        self.children: Dict[str, "MerkleNode"] = {}
        self.file_tree: Optional[BinaryMerkleNode] = None

    def to_dict(self) -> dict:
        d = {
            "name": self.name,
            "type": self.type.value,
            "path": self.path,
            "hash": self.hash,
            "children": {k: v.to_dict() for k, v in self.children.items()},
        }
        if self.file_tree is not None:
            d["file_tree"] = self.file_tree.to_dict()
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "MerkleNode":
        node = cls(data["name"], NodeType(data["type"]), data["path"])
        node.hash = data.get("hash", "")
        for child_name, child_data in data.get("children", {}).items():
            node.children[child_name] = cls.from_dict(child_data)
        if "file_tree" in data and data["file_tree"]:
            node.file_tree = BinaryMerkleNode.from_dict(data["file_tree"])
        return node


# ── Hash computation ────────────────────────────────────────────────────────

def compute_file_hash(filepath: str) -> str:
    """SHA-256 of file contents, read in 8KB blocks."""
    sha = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for block in iter(lambda: f.read(8192), b""):
                sha.update(block)
        return sha.hexdigest()
    except Exception:
        return ""


# ── Tree construction ──────────────────────────────────────────────────────

def build_merkle_tree(path: str) -> MerkleNode:
    """
    Build a hybrid Merkle tree rooted at *path*.

    - Directories: N-ary children (subdirs) + binary Merkle tree (files)
    - Files: SHA-256 content hash as binary tree leaves
    - Directory hash: SHA-256(sorted subdir hashes + file_tree root hash)
    """
    name = os.path.basename(path.rstrip(os.sep)) or path
    abs_path = os.path.abspath(path)

    if os.path.isfile(path):
        node = MerkleNode(name, NodeType.FILE, abs_path)
        node.hash = compute_file_hash(path)
        return node

    node = MerkleNode(name, NodeType.DIR, abs_path)

    try:
        entries = sorted(os.listdir(path))
    except Exception:
        entries = []

    file_leaves: List[BinaryMerkleNode] = []
    hash_parts: List[str] = []

    for entry in entries:
        if _should_skip(entry):
            continue

        full_path = os.path.join(path, entry)

        if os.path.isdir(full_path):
            child = build_merkle_tree(full_path)
            node.children[entry] = child
            hash_parts.append(child.hash)
        elif os.path.isfile(full_path):
            fhash = compute_file_hash(full_path)
            leaf = BinaryMerkleNode(hash_val=fhash, leaf_path=os.path.abspath(full_path))
            file_leaves.append(leaf)

    if file_leaves:
        node.file_tree = _build_binary_tree(file_leaves)
        hash_parts.append(node.file_tree.hash)

    node.hash = hashlib.sha256("".join(hash_parts).encode()).hexdigest()
    return node


# ── Tree diff ──────────────────────────────────────────────────────────────

def _collect_all_files(node: MerkleNode, acc: List[str]) -> None:
    """Recursively collect all file paths from a MerkleNode."""
    if node.type == NodeType.FILE:
        acc.append(node.path)
        return
    if node.file_tree:
        _collect_binary_leaves(node.file_tree, acc)
    for child in node.children.values():
        _collect_all_files(child, acc)


def _compare_nodes(
    old: MerkleNode, new: MerkleNode, diffs: Dict[str, List[str]]
) -> None:
    """
    Compare two directory MerkleNodes.
    - File level: binary tree diff → O(k log n) per directory
    - Subdir level: set diff for adds/removes, recurse on shared
    """
    # --- Binary diff of files within this directory ---
    old_ft = old.file_tree
    new_ft = new.file_tree

    if old_ft is not None and new_ft is not None:
        if old_ft.hash != new_ft.hash:
            _diff_binary_trees(old_ft, new_ft, diffs["modified"], diffs["added"], diffs["removed"])
    elif old_ft is None and new_ft is not None:
        _collect_binary_leaves(new_ft, diffs["added"])
    elif old_ft is not None and new_ft is None:
        _collect_binary_leaves(old_ft, diffs["removed"])

    # --- N-ary diff of subdirectories ---
    old_dirs = set(old.children.keys())
    new_dirs = set(new.children.keys())

    for name in new_dirs - old_dirs:
        _collect_all_files(new.children[name], diffs["added"])

    for name in old_dirs - new_dirs:
        _collect_all_files(old.children[name], diffs["removed"])

    for name in old_dirs & new_dirs:
        if old.children[name].hash != new.children[name].hash:
            _compare_nodes(old.children[name], new.children[name], diffs)


def get_merkle_diff(
    old_node: Union[MerkleNode, dict, None], new_node: MerkleNode
) -> Dict[str, List[str]]:
    """
    Compute diff between old and new Merkle trees.
    Returns dict with keys: added, removed, modified.
    """
    if isinstance(old_node, dict) and old_node:
        try:
            old_node = MerkleNode.from_dict(old_node)
        except Exception:
            old_node = None

    if not isinstance(old_node, MerkleNode):
        all_files: List[str] = []
        _collect_all_files(new_node, all_files)
        return {"added": all_files, "removed": [], "modified": []}

    diffs: Dict[str, List[str]] = {"added": [], "removed": [], "modified": []}

    if old_node.hash == new_node.hash:
        return diffs

    _compare_nodes(old_node, new_node, diffs)
    return diffs
