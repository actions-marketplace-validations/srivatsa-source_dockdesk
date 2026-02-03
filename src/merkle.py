import os
import hashlib
from enum import Enum
from typing import Dict, List, Union

class NodeType(str, Enum):
    FILE = "file"
    DIR = "dir"

class MerkleNode:
    def __init__(self, name: str, node_type: NodeType, path: str):
        self.name = name
        self.type = node_type
        self.path = path
        self.hash: str = ""
        self.children: Dict[str, "MerkleNode"] = {}

    def to_dict(self):
        return {
            "name": self.name,
            "type": self.type,
            "path": self.path,
            "hash": self.hash,
            "children": {k: v.to_dict() for k, v in self.children.items()}
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MerkleNode":
        node = cls(data["name"], NodeType(data["type"]), data["path"])
        node.hash = data.get("hash", "")
        for child_name, child_data in data.get("children", {}).items():
            node.children[child_name] = cls.from_dict(child_data)
        return node

def compute_file_hash(filepath: str) -> str:
    sha256_hash = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception:
        return ""

def build_merkle_tree(path: str) -> MerkleNode:
    name = os.path.basename(path.rstrip(os.sep)) or path
    if os.path.isfile(path):
        node = MerkleNode(name, NodeType.FILE, os.path.abspath(path))
        node.hash = compute_file_hash(path)
        return node

    node = MerkleNode(name, NodeType.DIR, os.path.abspath(path))
    child_hashes: List[str] = []
    try:
        entries = sorted(os.listdir(path))
    except Exception:
        entries = []

    for entry in entries:
        full_path = os.path.join(path, entry)
        if entry.startswith('.') or entry in ('__pycache__', '.venv', 'legacy'):
            continue
        child_node = build_merkle_tree(full_path)
        if child_node:
            node.children[entry] = child_node
            child_hashes.append(child_node.hash)

    node.hash = hashlib.sha256("".join(child_hashes).encode()).hexdigest()
    return node

def _collect_all_files(node: MerkleNode, acc: List[str]):
    if node.type == NodeType.FILE:
        acc.append(node.path)
        return
    for child in node.children.values():
        _collect_all_files(child, acc)

def _compare_nodes(old: MerkleNode, new: MerkleNode, diffs: Dict[str, List[str]]):
    if old.type == NodeType.FILE and new.type == NodeType.FILE:
        if old.hash != new.hash:
            diffs["modified"].append(new.path)
        return
    old_children = set(old.children.keys())
    new_children = set(new.children.keys())
    for name in new_children - old_children:
        _collect_all_files(new.children[name], diffs["added"])
    for name in old_children - new_children:
        _collect_all_files(old.children[name], diffs["removed"])
    for name in old_children & new_children:
        if old.children[name].hash != new.children[name].hash:
            _compare_nodes(old.children[name], new.children[name], diffs)

def get_merkle_diff(old_node: Union[MerkleNode, dict], new_node: MerkleNode) -> Dict[str, List[str]]:
    if isinstance(old_node, dict) and old_node:
        try:
            old_node = MerkleNode.from_dict(old_node)
        except Exception:
            old_node = None
    if not isinstance(old_node, MerkleNode):
        old_node = new_node  # no prior snapshot
    diffs = {"added": [], "removed": [], "modified": []}
    if old_node.hash == new_node.hash:
        return diffs
    _compare_nodes(old_node, new_node, diffs)
    return diffs
