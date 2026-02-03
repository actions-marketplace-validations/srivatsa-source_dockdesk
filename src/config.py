"""
DockDesk Configuration System

Unified config with priority: CLI args > env vars > config file > defaults
"""

import os
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum

# Config file names (checked in order)
CONFIG_FILES = ["dockdesk.yml", "dockdesk.yaml", "dockdesk.json", ".dockdeskrc"]


class OutputFormat(str, Enum):
    MARKDOWN = "md"
    JSON = "json"
    SARIF = "sarif"  # For IDE integration


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    
    @classmethod
    def from_string(cls, value: str) -> "RiskLevel":
        return cls[value.upper()]
    
    def __lt__(self, other):
        order = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2}
        return order[self] < order[other]
    
    def __le__(self, other):
        return self == other or self < other


@dataclass
class DockDeskConfig:
    """Complete configuration for DockDesk auditor."""
    
    # Core settings
    workspace: str = "."
    model: str = "qwen2.5-coder:3b"
    ollama_host: str = "http://localhost:11434"
    temperature: float = 0.1
    
    # Behavior flags
    auto_tune: bool = False
    auto_fix: bool = False
    fix_code: bool = False  # Opt-in for code fixes (not just docs)
    ci_mode: bool = False
    verbose: bool = False
    
    # Output settings
    output_format: OutputFormat = OutputFormat.MARKDOWN
    output_file: Optional[str] = None
    
    # Guardrails
    fail_on_risk: RiskLevel = RiskLevel.HIGH
    max_files: int = 100  # Limit files per audit
    timeout_per_file: int = 120  # Seconds
    
    # Dashboard
    enable_changelog: bool = True
    changelog_file: str = "audit_history.jsonl"
    
    # Advanced
    skip_rag: bool = False
    force_full_scan: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "workspace": self.workspace,
            "model": self.model,
            "ollama_host": self.ollama_host,
            "temperature": self.temperature,
            "auto_tune": self.auto_tune,
            "auto_fix": self.auto_fix,
            "fix_code": self.fix_code,
            "ci_mode": self.ci_mode,
            "verbose": self.verbose,
            "output_format": self.output_format.value,
            "output_file": self.output_file,
            "fail_on_risk": self.fail_on_risk.value,
            "max_files": self.max_files,
            "timeout_per_file": self.timeout_per_file,
            "enable_changelog": self.enable_changelog,
            "changelog_file": self.changelog_file,
            "skip_rag": self.skip_rag,
            "force_full_scan": self.force_full_scan,
        }


def load_config_file(workspace: str) -> Dict[str, Any]:
    """Load configuration from file if it exists."""
    for filename in CONFIG_FILES:
        config_path = Path(workspace) / filename
        if config_path.exists():
            try:
                content = config_path.read_text(encoding='utf-8')
                
                if filename.endswith(('.yml', '.yaml')):
                    try:
                        import yaml
                        return yaml.safe_load(content) or {}
                    except ImportError:
                        # Fallback: basic YAML parsing for simple configs
                        return _parse_simple_yaml(content)
                else:
                    return json.loads(content)
            except Exception:
                continue
    return {}


def _parse_simple_yaml(content: str) -> Dict[str, Any]:
    """Basic YAML parsing for simple key: value configs."""
    result = {}
    for line in content.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()
            
            # Type conversion
            if value.lower() in ('true', 'yes'):
                value = True
            elif value.lower() in ('false', 'no'):
                value = False
            elif value.isdigit():
                value = int(value)
            elif value.replace('.', '').isdigit():
                value = float(value)
            elif value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]
                
            result[key] = value
    return result


def load_env_config() -> Dict[str, Any]:
    """Load configuration from environment variables."""
    env_map = {
        "DOCKDESK_MODEL": "model",
        "DOCKDESK_OLLAMA_HOST": "ollama_host",
        "DOCKDESK_OUTPUT_FORMAT": "output_format",
        "DOCKDESK_FAIL_ON_RISK": "fail_on_risk",
        "DOCKDESK_AUTO_FIX": "auto_fix",
        "DOCKDESK_VERBOSE": "verbose",
        "DOCKDESK_SKIP_RAG": "skip_rag",
        "DOCKDESK_CHANGELOG": "enable_changelog",
        # Legacy support
        "MODEL_NAME": "model",
        "OLLAMA_URL": "ollama_host",
    }
    
    result = {}
    for env_var, config_key in env_map.items():
        value = os.getenv(env_var)
        if value is not None:
            # Type conversion
            if config_key in ("auto_fix", "verbose", "skip_rag", "enable_changelog"):
                value = value.lower() in ('true', '1', 'yes')
            result[config_key] = value
    
    return result


def build_config(
    cli_args: Optional[Dict[str, Any]] = None,
    workspace: str = "."
) -> DockDeskConfig:
    """
    Build configuration with priority: CLI > env > file > defaults
    
    Args:
        cli_args: Arguments from CLI parser
        workspace: Workspace path for config file lookup
        
    Returns:
        Complete DockDeskConfig instance
    """
    # Start with defaults
    config = DockDeskConfig()
    
    # Layer 1: Config file
    file_config = load_config_file(workspace)
    for key, value in file_config.items():
        if hasattr(config, key):
            if key == "output_format" and isinstance(value, str):
                value = OutputFormat(value)
            elif key == "fail_on_risk" and isinstance(value, str):
                value = RiskLevel.from_string(value)
            setattr(config, key, value)
    
    # Layer 2: Environment variables
    env_config = load_env_config()
    for key, value in env_config.items():
        if hasattr(config, key):
            if key == "output_format" and isinstance(value, str):
                value = OutputFormat(value)
            elif key == "fail_on_risk" and isinstance(value, str):
                value = RiskLevel.from_string(value)
            setattr(config, key, value)
    
    # Layer 3: CLI arguments (highest priority)
    if cli_args:
        for key, value in cli_args.items():
            if value is not None and hasattr(config, key):
                if key == "output_format" and isinstance(value, str):
                    value = OutputFormat(value)
                elif key == "fail_on_risk" and isinstance(value, str):
                    value = RiskLevel.from_string(value)
                setattr(config, key, value)
    
    # Ensure workspace is absolute
    config.workspace = os.path.abspath(config.workspace)
    
    return config


def create_sample_config(workspace: str, format: str = "yaml") -> str:
    """Generate a sample configuration file."""
    if format == "yaml":
        return """# DockDesk Configuration
# Place this file as dockdesk.yml in your project root

# Model Selection
model: qwen2.5-coder:3b  # Use --list-models to see options
ollama_host: http://localhost:11434
temperature: 0.1

# Behavior
auto_tune: false      # Auto-select model based on codebase size
auto_fix: false       # Automatically apply documentation fixes
fix_code: false       # Also fix code (not just docs) - use with caution

# Output
output_format: md     # md, json, or sarif
# output_file: audit_report.md  # Custom output path

# Guardrails
fail_on_risk: HIGH    # Fail CI on HIGH, MEDIUM, or LOW risk findings
max_files: 100        # Maximum files to audit per run
timeout_per_file: 120 # Seconds per file

# Dashboard
enable_changelog: true
changelog_file: audit_history.jsonl
"""
    else:
        return json.dumps(DockDeskConfig().to_dict(), indent=2)
