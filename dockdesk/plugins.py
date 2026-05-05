"""
DockDesk Plugin System - Custom validation hooks.

Loads Python plugins from .dockdesk/plugins/ in the workspace.
Each plugin can define:
  - pre_audit(files: list[str], config: dict) -> list[str]   (filter/modify file list)
  - post_audit(results: list[dict]) -> list[dict]            (filter/augment results)

Security note: Plugins execute arbitrary Python. A disclaimer is printed on first load.
"""

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from rich.console import Console

console = Console(highlight=False)

PLUGINS_DIR_NAME = ".dockdesk/plugins"


class Plugin:
    """Wrapper around a single loaded plugin module."""

    def __init__(self, name: str, module: Any):
        self.name = name
        self.module = module
        self.pre_audit: Optional[Callable] = getattr(module, "pre_audit", None)
        self.post_audit: Optional[Callable] = getattr(module, "post_audit", None)

    def __repr__(self) -> str:
        hooks = []
        if self.pre_audit:
            hooks.append("pre_audit")
        if self.post_audit:
            hooks.append("post_audit")
        return f"Plugin({self.name}, hooks=[{', '.join(hooks)}])"


class PluginManager:
    """Discovers and runs workspace plugins."""

    def __init__(self, workspace: str):
        self.workspace = workspace
        self.plugins_dir = Path(workspace) / PLUGINS_DIR_NAME
        self._plugins: List[Plugin] = []
        self._loaded = False

    def discover(self) -> "PluginManager":
        """Scan the plugins directory and load all .py files."""
        if self._loaded:
            return self

        if not self.plugins_dir.is_dir():
            self._loaded = True
            return self

        py_files = sorted(self.plugins_dir.glob("*.py"))
        if not py_files:
            self._loaded = True
            return self

        # Security disclaimer
        console.print(
            f"[yellow] Loading {len(py_files)} plugin(s) from "
            f"{self.plugins_dir}[/yellow]"
        )
        console.print(
            "[dim]  Plugins execute arbitrary code. "
            "Review them before use.[/dim]"
        )

        for py_file in py_files:
            try:
                name = py_file.stem
                spec = importlib.util.spec_from_file_location(
                    f"dockdesk_plugin_{name}", str(py_file)
                )
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    sys.modules[f"dockdesk_plugin_{name}"] = mod
                    spec.loader.exec_module(mod)
                    plugin = Plugin(name, mod)
                    self._plugins.append(plugin)
                    console.print(
                        f"[dim]   Loaded plugin: {name} ({plugin})[/dim]"
                    )
            except Exception as e:
                console.print(
                    f"[red]  ✗ Failed to load plugin {py_file.name}: {e}[/red]"
                )

        self._loaded = True
        return self

    @property
    def has_plugins(self) -> bool:
        return len(self._plugins) > 0

    @property
    def count(self) -> int:
        return len(self._plugins)

    def run_pre_hooks(
        self, files: List[str], config: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """Run all pre_audit hooks. Plugins can filter or reorder the file list."""
        result = list(files)
        for plugin in self._plugins:
            if plugin.pre_audit:
                try:
                    modified = plugin.pre_audit(result, config or {})
                    if isinstance(modified, list):
                        result = modified
                except Exception as e:
                    console.print(
                        f"[yellow]   Plugin '{plugin.name}' pre_audit "
                        f"failed: {e}[/yellow]"
                    )
        return result

    def run_post_hooks(self, results: List[Dict]) -> List[Dict]:
        """Run all post_audit hooks. Plugins can augment or filter results."""
        current = list(results)
        for plugin in self._plugins:
            if plugin.post_audit:
                try:
                    modified = plugin.post_audit(current)
                    if isinstance(modified, list):
                        current = modified
                except Exception as e:
                    console.print(
                        f"[yellow]   Plugin '{plugin.name}' post_audit "
                        f"failed: {e}[/yellow]"
                    )
        return current
