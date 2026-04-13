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
    model: str = "qwen2.5-coder:7b"
    detect_model: str = ""   # Phase 1 detection model (empty = use 'model') [DEPRECATED: use reasoning_model]
    fix_model: str = ""      # Phase 2 fix-generation model (empty = use 'model') [DEPRECATED: use reasoning_model]
    reasoning_model: str = ""  # Logical reasoning model — DeepSeek-R1 (empty = use default)
    discord_webhook: str = ""  # Discord webhook URL for audit notifications
    discord_bot_token: str = ""  # Discord bot token for slash-command bot mode
    discord_bot_guild_id: str = ""  # Optional guild ID to scope slash command sync
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
    max_files: int = 0  # 0 = no limit (was 100 but never enforced; now wired)
    timeout_per_file: int = 120  # Seconds
    max_file_size: int = 512000  # 500 KB — skip binaries/lockfiles
    
    # Dashboard
    enable_changelog: bool = True
    changelog_file: str = "audit_history.jsonl"
    
    # Advanced
    skip_rag: bool = False
    force_full_scan: bool = False
    rotate_models: bool = False
    
    # Scaling (monorepo)
    include_patterns: str = ""   # Comma-separated globs, e.g. "src/**,lib/**"
    exclude_patterns: str = ""   # Comma-separated globs, e.g. "generated/**,vendor/**"
    workers: int = 0             # 0 = auto-detect from pool size
    fast_mode: bool = False      # Skip reasoning for LOW-risk findings
    clear_cache: bool = False    # Wipe cache before run
    batch_size: int = 5          # Files per batched LLM call (code analysis)
    ollama_urls: str = ""        # Comma-separated Ollama endpoints
    respect_gitignore: bool = True
    turbo: bool = False           # Aggressive speed mode: --fast --batch-size 8 --workers 4 --skip-rag
    custom_rules: List[str] = field(default_factory=list)  # User-defined audit rules injected into LLM prompts
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "workspace": self.workspace,
            "model": self.model,
            "detect_model": self.detect_model,
            "fix_model": self.fix_model,
            "reasoning_model": self.reasoning_model,
            "discord_webhook": self.discord_webhook,
            "discord_bot_token": self.discord_bot_token,
            "discord_bot_guild_id": self.discord_bot_guild_id,
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
            "max_file_size": self.max_file_size,
            "enable_changelog": self.enable_changelog,
            "changelog_file": self.changelog_file,
            "skip_rag": self.skip_rag,
            "force_full_scan": self.force_full_scan,
            "rotate_models": self.rotate_models,
            "include_patterns": self.include_patterns,
            "exclude_patterns": self.exclude_patterns,
            "workers": self.workers,
            "fast_mode": self.fast_mode,
            "clear_cache": self.clear_cache,
            "batch_size": self.batch_size,
            "ollama_urls": self.ollama_urls,
            "respect_gitignore": self.respect_gitignore,
            "turbo": self.turbo,
            "custom_rules": self.custom_rules,
        }

    def get_include_list(self) -> List[str]:
        """Parse comma-separated include patterns."""
        return [p.strip() for p in self.include_patterns.split(',') if p.strip()] if self.include_patterns else []

    def get_exclude_list(self) -> List[str]:
        """Parse comma-separated exclude patterns."""
        return [p.strip() for p in self.exclude_patterns.split(',') if p.strip()] if self.exclude_patterns else []

    def get_ollama_url_list(self) -> List[str]:
        """Parse comma-separated Ollama URLs."""
        return [u.strip() for u in self.ollama_urls.split(',') if u.strip()] if self.ollama_urls else []


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
    """Basic YAML parsing for simple key: value configs, with list support."""
    result = {}
    current_key = None
    current_list: Optional[List[str]] = None
    lines = content.split('\n')
    
    for i, raw_line in enumerate(lines):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        
        # Check for list item (starts with '- ')
        if stripped.startswith('- ') and current_key is not None:
            item = stripped[2:].strip()
            # Strip quotes
            if (item.startswith('"') and item.endswith('"')) or (item.startswith("'") and item.endswith("'")):
                item = item[1:-1]
            if current_list is None:
                current_list = []
            current_list.append(item)
            continue
        
        # Flush any accumulated list
        if current_key is not None and current_list is not None:
            result[current_key] = current_list
            current_list = None
            current_key = None
        
        if ':' in stripped:
            key, value = stripped.split(':', 1)
            key = key.strip()
            value = value.strip()
            
            # Empty value after colon means upcoming list
            if value == '' or value == '[]':
                current_key = key
                current_list = [] if value == '[]' else None
                continue
            
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
            current_key = None
            current_list = None
    
    # Flush trailing list
    if current_key is not None and current_list is not None:
        result[current_key] = current_list
    
    return result


def load_env_config() -> Dict[str, Any]:
    """Load configuration from environment variables."""
    env_map = {
        "DOCKDESK_MODEL": "model",
        "DOCKDESK_DETECT_MODEL": "detect_model",
        "DOCKDESK_FIX_MODEL": "fix_model",
        "DOCKDESK_REASONING_MODEL": "reasoning_model",
        "DOCKDESK_DISCORD_WEBHOOK": "discord_webhook",
        "DOCKDESK_DISCORD_BOT_TOKEN": "discord_bot_token",
        "DOCKDESK_DISCORD_BOT_GUILD_ID": "discord_bot_guild_id",
        "DOCKDESK_OLLAMA_HOST": "ollama_host",
        "DOCKDESK_OUTPUT_FORMAT": "output_format",
        "DOCKDESK_FAIL_ON_RISK": "fail_on_risk",
        "DOCKDESK_AUTO_FIX": "auto_fix",
        "DOCKDESK_VERBOSE": "verbose",
        "DOCKDESK_SKIP_RAG": "skip_rag",
        "DOCKDESK_CHANGELOG": "enable_changelog",
        "DOCKDESK_ROTATE_MODELS": "rotate_models",
        # Legacy support
        "MODEL_NAME": "model",
        "OLLAMA_URL": "ollama_host",
    }
    
    result = {}
    for env_var, config_key in env_map.items():
        value = os.getenv(env_var)
        if value is not None:
            # Type conversion
            if config_key in ("auto_fix", "verbose", "skip_rag", "enable_changelog", "rotate_models"):
                value = value.lower() in ('true', '1', 'yes')
            result[config_key] = value
    
    return result


def _apply_layer(config: "DockDeskConfig", layer: Dict[str, Any]) -> None:
    """Apply a dict of settings to a config object with type coercion."""
    for key, value in layer.items():
        if not hasattr(config, key) or value is None:
            continue
        if key == "output_format" and isinstance(value, str):
            value = OutputFormat(value)
        elif key == "fail_on_risk" and isinstance(value, str):
            value = RiskLevel.from_string(value)
        setattr(config, key, value)


def build_config(
    cli_args: Optional[Dict[str, Any]] = None,
    workspace: str = ".",
    profile: Optional[str] = None,
) -> DockDeskConfig:
    """
    Build configuration with priority: CLI > env > workspace file > profile > global > defaults
    
    Args:
        cli_args: Arguments from CLI parser
        workspace: Workspace path for config file lookup
        profile: Optional named profile to load
        
    Returns:
        Complete DockDeskConfig instance
    """
    # Start with defaults
    config = DockDeskConfig()

    # Layer 0: Global config (~/.config/dockdesk/config.yml)
    try:
        from .profiles import get_global_config
        _apply_layer(config, get_global_config())
    except Exception:
        pass

    # Layer 0.5: Named profile
    if profile:
        try:
            from .profiles import load_profile
            _apply_layer(config, load_profile(profile))
        except Exception:
            pass
    
    # Layer 1: Workspace config file
    _apply_layer(config, load_config_file(workspace))
    
    # Layer 2: Environment variables
    _apply_layer(config, load_env_config())
    
    # Layer 3: CLI arguments (highest priority)
    if cli_args:
        # Filter out None values so defaults aren't overwritten
        filtered = {k: v for k, v in cli_args.items() if v is not None}
        _apply_layer(config, filtered)
    
    # Ensure workspace is absolute
    config.workspace = os.path.abspath(config.workspace)
    
    return config


def create_sample_config(workspace: str, format: str = "yaml") -> str:
    """Generate a sample configuration file."""
    if format == "yaml":
        return """# DockDesk Configuration
# Place this file as dockdesk.yml in your project root

# Model Selection
model: qwen2.5-coder:7b  # Use --list-models to see options
ollama_host: http://localhost:11434
temperature: 0.1

# Dual-Model Pipeline (optional — leave empty to use 'model' for both)
# detect_model: deepseek-r1:1.5b    # Fast reasoning model for Phase 1 detection
# fix_model: qwen2.5-coder:3b       # Code-capable model for Phase 2 fix generation

# Discord
# discord_webhook: https://discord.com/api/webhooks/...
# discord_bot_token: <bot-token>
# discord_bot_guild_id: <guild-id>

# Behavior
auto_tune: false      # Auto-select model based on codebase size
auto_fix: false       # Automatically apply documentation fixes
fix_code: false       # Also fix code (not just docs) - use with caution
rotate_models: false  # Round-robin code analysis model per file (requires local models)

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

# Custom Audit Rules (injected into LLM prompts)
# custom_rules:
#   - "Flag any hardcoded secrets or API keys in code"
#   - "Ensure all public functions have docstrings"
#   - "Check that error handling matches documentation"
"""
    else:
        return json.dumps(DockDeskConfig().to_dict(), indent=2)
