import ast
import os
from typing import List, Dict, Tuple

def get_file_dependencies(file_path: str, root_dir: str) -> List[str]:
    """
    Parses a python file and resolves its imports to file paths 
    relative to the project root.
    """
    deps = []
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=file_path)
    except Exception:
        return []

    for node in ast.walk(tree):
        imported_module = None
        
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_module = alias.name

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_module = node.module
            else:
                # Relative import logic simplified
                imported_module = "RELATIVE"

        if imported_module and imported_module != "RELATIVE":
            # Attempt to resolve "src.utils" -> "src/utils.py"
            potential_path = os.path.join(root_dir, *imported_module.split(".")) + ".py"
            if os.path.exists(potential_path):
                deps.append(potential_path)
                
    return deps

def build_dependency_graphs(root_path: str) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    """
    Builds both forward (file->imports) and reverse (file->dependents) graphs.
    """
    forward_graph = {} 
    reverse_graph = {} 

    for root, _, files in os.walk(root_path):
        if '.venv' in root or 'legacy' in root: continue
        
        for file in files:
            if file.endswith(".py"):
                full_path = os.path.join(root, file)
                full_path = os.path.abspath(full_path)
                
                if full_path not in forward_graph:
                    forward_graph[full_path] = []
                if full_path not in reverse_graph: 
                    reverse_graph[full_path] = []

                imports = get_file_dependencies(full_path, root_path)
                # Normalize import paths
                imports = [os.path.abspath(p) for p in imports]
                forward_graph[full_path] = imports

    # Invert
    for source_file, dependencies in forward_graph.items():
        for dep in dependencies:
            if dep not in reverse_graph:
                reverse_graph[dep] = []
            if source_file not in reverse_graph[dep]:
                reverse_graph[dep].append(source_file)

    return forward_graph, reverse_graph
