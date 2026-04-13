"""
DockDesk Profiles — Global configuration & named profile support.

Loads settings from:
  1. ~/.config/dockdesk/config.yml   (global defaults)
  2. ~/.config/dockdesk/profiles/<name>.yml  (named profiles)

Profiles are layered BETWEEN global config and workspace config in the
priority chain:  CLI > env > workspace file > profile > global > defaults
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, List

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console(highlight=False)

# ── Paths ──────────────────────────────────────────────────────────────────────
_CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
GLOBAL_CONFIG_DIR = _CONFIG_HOME / "dockdesk"
GLOBAL_CONFIG_FILE = GLOBAL_CONFIG_DIR / "config.yml"
PROFILES_DIR = GLOBAL_CONFIG_DIR / "profiles"

# Built-in profile presets (used when `dockdesk profile create <name>`)
BUILTIN_PROFILES: Dict[str, Dict[str, Any]] = {
    "strict": {
        "fail_on_risk": "MEDIUM",
        "auto_tune": True,
        "skip_rag": False,
        "fast_mode": False,
        "verbose": True,
        "description": "Maximum rigour — flags MEDIUM+ risk, uses RAG, verbose output",
    },
    "fast": {
        "fail_on_risk": "HIGH",
        "auto_tune": False,
        "skip_rag": True,
        "fast_mode": True,
        "turbo": True,
        "description": "Speed-optimised — turbo mode, skip RAG, only block on HIGH risk",
    },
    "ci": {
        "fail_on_risk": "HIGH",
        "ci_mode": True,
        "skip_rag": True,
        "fast_mode": True,
        "verbose": False,
        "enable_changelog": True,
        "description": "CI/CD pipeline — non-interactive, fast, exits with code on failure",
    },
}


def _ensure_dirs() -> None:
    """Create global config directories if they don't exist."""
    GLOBAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)


def _parse_yaml_simple(content: str) -> Dict[str, Any]:
    """Lightweight YAML parser for key: value configs."""
    try:
        import yaml
        return yaml.safe_load(content) or {}
    except ImportError:
        # Minimal fallback
        from .config import _parse_simple_yaml
        return _parse_simple_yaml(content)


def _dump_yaml(data: Dict[str, Any]) -> str:
    """Dump dict to YAML string."""
    try:
        import yaml
        return yaml.dump(data, default_flow_style=False, sort_keys=False)
    except ImportError:
        lines = []
        for k, v in data.items():
            if isinstance(v, bool):
                lines.append(f"{k}: {'true' if v else 'false'}")
            elif isinstance(v, list):
                lines.append(f"{k}:")
                for item in v:
                    lines.append(f"  - {item}")
            else:
                lines.append(f"{k}: {v}")
        return "\n".join(lines) + "\n"


# ── Public API ─────────────────────────────────────────────────────────────────

def get_global_config() -> Dict[str, Any]:
    """Load the global config file (~/.config/dockdesk/config.yml)."""
    if not GLOBAL_CONFIG_FILE.exists():
        return {}
    try:
        content = GLOBAL_CONFIG_FILE.read_text(encoding="utf-8")
        return _parse_yaml_simple(content)
    except Exception:
        return {}


def load_profile(name: str) -> Dict[str, Any]:
    """Load a named profile by name.

    Looks for ~/.config/dockdesk/profiles/<name>.yml first,
    then falls back to built-in presets.
    """
    profile_path = PROFILES_DIR / f"{name}.yml"
    if profile_path.exists():
        try:
            content = profile_path.read_text(encoding="utf-8")
            data = _parse_yaml_simple(content)
            data.pop("description", None)  # strip metadata
            return data
        except Exception:
            pass

    # Built-in preset
    if name in BUILTIN_PROFILES:
        preset = dict(BUILTIN_PROFILES[name])
        preset.pop("description", None)
        return preset

    return {}


def list_profiles() -> List[Dict[str, str]]:
    """List all available profiles (built-in + user-created)."""
    profiles: List[Dict[str, str]] = []

    # Built-in
    for name, data in BUILTIN_PROFILES.items():
        profiles.append({
            "name": name,
            "source": "built-in",
            "description": data.get("description", ""),
        })

    # User-created (on disk)
    _ensure_dirs()
    for f in sorted(PROFILES_DIR.glob("*.yml")):
        name = f.stem
        if name in BUILTIN_PROFILES:
            # User override of built-in
            profiles = [p for p in profiles if p["name"] != name]
        try:
            content = _parse_yaml_simple(f.read_text(encoding="utf-8"))
            desc = content.get("description", "User-created profile")
        except Exception:
            desc = "User-created profile"
        profiles.append({
            "name": name,
            "source": "user",
            "description": desc,
        })

    return profiles


def create_profile(name: str, overrides: Optional[Dict[str, Any]] = None) -> Path:
    """Create a new profile YAML file.

    If `name` matches a built-in, the built-in defaults are used as a base,
    then `overrides` are merged on top.
    """
    _ensure_dirs()
    base = dict(BUILTIN_PROFILES.get(name, {}))
    if overrides:
        base.update(overrides)
    if "description" not in base:
        base["description"] = f"Custom profile: {name}"

    profile_path = PROFILES_DIR / f"{name}.yml"
    profile_path.write_text(
        f"# DockDesk Profile: {name}\n" + _dump_yaml(base),
        encoding="utf-8",
    )
    return profile_path


def init_global_config() -> Path:
    """Create a sample global config file if one doesn't exist."""
    _ensure_dirs()
    if GLOBAL_CONFIG_FILE.exists():
        return GLOBAL_CONFIG_FILE

    sample = """\
# DockDesk Global Configuration
# Applies to ALL workspaces unless overridden by a project-level dockdesk.yml

# Default model
model: qwen2.5-coder:7b
reasoning_model: deepseek-r1:1.5b

# Default Ollama host
ollama_host: http://localhost:11434

# Discord webhook (optional — applies globally)
# discord_webhook: https://discord.com/api/webhooks/...

# Default behaviour
auto_tune: false
skip_rag: false
verbose: false
"""
    GLOBAL_CONFIG_FILE.write_text(sample, encoding="utf-8")
    return GLOBAL_CONFIG_FILE


# ── CLI rendering ──────────────────────────────────────────────────────────────

def print_profile_list() -> None:
    """Pretty-print all profiles."""
    from .ui import ORCHID, HOT_PINK, PURPLE, MAGENTA

    profiles = list_profiles()
    if not profiles:
        console.print("[yellow]No profiles found.[/yellow]")
        return

    table = Table(
        title="[bold #FF1493]DockDesk Profiles[/bold #FF1493]",
        box=box.ROUNDED,
        border_style=PURPLE,
        show_lines=True,
    )
    table.add_column("Name", style=f"bold {MAGENTA}", width=14)
    table.add_column("Source", style=f"dim {ORCHID}", width=10)
    table.add_column("Description", style=f"{HOT_PINK}")

    for p in profiles:
        source_badge = "⚡ built-in" if p["source"] == "built-in" else "👤 user"
        table.add_row(p["name"], source_badge, p["description"])

    console.print(table)


def print_profile_detail(name: str) -> None:
    """Pretty-print a single profile's settings."""
    from .ui import ORCHID, HOT_PINK, PURPLE

    data = load_profile(name)
    if not data:
        console.print(f"[bold red]Profile '{name}' not found.[/bold red]")
        return

    lines = []
    for k, v in data.items():
        lines.append(f"  [bold #DA70D6]{k}[/bold #DA70D6]: [#FF69B4]{v}[/#FF69B4]")

    console.print(Panel(
        "\n".join(lines),
        title=f"[bold #FF1493]Profile: {name}[/bold #FF1493]",
        border_style=PURPLE,
    ))
