"""
DockDesk Model Selection & Auto-Tuning System

Provides audit-suitable model allowlist and LOC-based auto-selection.
"""

import os
import subprocess
import json
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple
from enum import Enum
from rich.console import Console
from rich.table import Table

console = Console()


class ModelTier(str, Enum):
    SMALL = "small"      # < 5B params, fast, < 10k LOC
    MEDIUM = "medium"    # 5-10B params, balanced, 10k-50k LOC
    LARGE = "large"      # > 10B params, thorough, > 50k LOC


@dataclass
class AuditModel:
    """Definition of an audit-suitable model."""
    name: str
    tier: ModelTier
    params_b: float  # Billions of parameters
    description: str
    strengths: List[str]
    max_context: int = 4096
    recommended_loc: Tuple[int, int] = (0, 100000)  # min, max LOC range


# Allowlist of models verified for semantic auditing
AUDIT_MODELS: Dict[str, AuditModel] = {
    # Small tier (< 5B) - Fast, good for small projects
    "qwen2.5-coder:3b": AuditModel(
        name="qwen2.5-coder:3b",
        tier=ModelTier.SMALL,
        params_b=3.0,
        description="Fast, efficient coder model. Best for quick audits.",
        strengths=["Speed", "Low memory", "Good code understanding"],
        max_context=8192,
        recommended_loc=(0, 10000),
    ),
    "qwen2.5-coder:1.5b": AuditModel(
        name="qwen2.5-coder:1.5b",
        tier=ModelTier.SMALL,
        params_b=1.5,
        description="Ultra-fast, minimal resource usage.",
        strengths=["Fastest", "Lowest memory", "CI-friendly"],
        max_context=8192,
        recommended_loc=(0, 5000),
    ),
    "deepseek-coder:1.3b": AuditModel(
        name="deepseek-coder:1.3b",
        tier=ModelTier.SMALL,
        params_b=1.3,
        description="Compact coder with strong reasoning.",
        strengths=["Compact", "Good at diffs", "Fast inference"],
        max_context=4096,
        recommended_loc=(0, 5000),
    ),
    "deepseek-r1:1.5b": AuditModel(
        name="deepseek-r1:1.5b",
        tier=ModelTier.SMALL,
        params_b=1.5,
        description="DeepSeek R1 distilled reasoning model. Chain-of-thought risk assessor.",
        strengths=["Logical reasoning", "Chain-of-thought", "Risk assessment", "Safety judgement"],
        max_context=8192,
        recommended_loc=(0, 10000),
    ),
    "starcoder2:3b": AuditModel(
        name="starcoder2:3b",
        tier=ModelTier.SMALL,
        params_b=3.0,
        description="Code-focused model from BigCode.",
        strengths=["Multi-language", "Code completion", "Documentation"],
        max_context=4096,
        recommended_loc=(0, 10000),
    ),
    
    # Medium tier (5-10B) - Balanced performance
    "qwen2.5-coder:7b": AuditModel(
        name="qwen2.5-coder:7b",
        tier=ModelTier.MEDIUM,
        params_b=7.0,
        description="Balanced performance and quality.",
        strengths=["Accurate", "Good reasoning", "Detailed fixes"],
        max_context=32768,
        recommended_loc=(5000, 50000),
    ),
    "codellama:7b": AuditModel(
        name="codellama:7b",
        tier=ModelTier.MEDIUM,
        params_b=7.0,
        description="Meta's code-specialized Llama.",
        strengths=["Strong code understanding", "Good at Python/JS", "Reliable"],
        max_context=16384,
        recommended_loc=(5000, 50000),
    ),
    "deepseek-coder:6.7b": AuditModel(
        name="deepseek-coder:6.7b",
        tier=ModelTier.MEDIUM,
        params_b=6.7,
        description="DeepSeek's mid-tier coder.",
        strengths=["Balanced", "Good reasoning", "Multi-language"],
        max_context=16384,
        recommended_loc=(5000, 50000),
    ),
    
    # Large tier (> 10B) - Thorough, for large codebases
    "qwen2.5-coder:14b": AuditModel(
        name="qwen2.5-coder:14b",
        tier=ModelTier.LARGE,
        params_b=14.0,
        description="High-quality audits for large projects.",
        strengths=["Most accurate", "Complex reasoning", "Detailed analysis"],
        max_context=32768,
        recommended_loc=(20000, 500000),
    ),
    "codellama:13b": AuditModel(
        name="codellama:13b",
        tier=ModelTier.LARGE,
        params_b=13.0,
        description="Larger CodeLlama for thorough audits.",
        strengths=["Thorough", "Good at edge cases", "Strong reasoning"],
        max_context=16384,
        recommended_loc=(20000, 200000),
    ),
    "deepseek-coder:33b": AuditModel(
        name="deepseek-coder:33b",
        tier=ModelTier.LARGE,
        params_b=33.0,
        description="Most powerful, for enterprise codebases.",
        strengths=["Enterprise-grade", "Best accuracy", "Complex analysis"],
        max_context=16384,
        recommended_loc=(50000, 1000000),
    ),
}

# Default model for quick starts
DEFAULT_MODEL = "qwen2.5-coder:3b"

# Default reasoning model (DeepSeek-R1 for logical risk assessment)
DEFAULT_REASONING_MODEL = "deepseek-r1:1.5b"


# Module-level cache for ollama model list (avoid repeated subprocess calls)
_ollama_models_cache: Optional[List[str]] = None


def get_available_ollama_models() -> List[str]:
    """Query Ollama for locally available models. Cached per session."""
    global _ollama_models_cache
    if _ollama_models_cache is not None:
        return _ollama_models_cache
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            _ollama_models_cache = []
            return []
        
        lines = result.stdout.strip().split("\n")[1:]  # Skip header
        models = []
        for line in lines:
            if line.strip():
                model_name = line.split()[0]
                models.append(model_name)
        _ollama_models_cache = models
        return models
    except Exception:
        _ollama_models_cache = []
        return []


def is_model_audit_suitable(model_name: str) -> bool:
    """Check if a model is in the audit-suitable allowlist."""
    # Exact match
    if model_name in AUDIT_MODELS:
        return True
    
    # Partial match (e.g., "qwen2.5-coder:3b-instruct" matches "qwen2.5-coder")
    base_name = model_name.split(":")[0] if ":" in model_name else model_name
    for allowed in AUDIT_MODELS.keys():
        allowed_base = allowed.split(":")[0]
        if base_name == allowed_base:
            return True
    
    return False


def get_model_info(model_name: str) -> Optional[AuditModel]:
    """Get model info, with fallback for variants."""
    if model_name in AUDIT_MODELS:
        return AUDIT_MODELS[model_name]
    
    # Try base name match
    base_name = model_name.split(":")[0] if ":" in model_name else model_name
    for name, model in AUDIT_MODELS.items():
        if name.split(":")[0] == base_name:
            return model
    
    return None


def count_lines_of_code(workspace: str, file_list: Optional[List[str]] = None) -> int:
    """Count total lines of code in workspace.
    
    If file_list is provided, counts only those files (faster when discovery already ran).
    Otherwise falls back to a full os.walk.
    """
    total_loc = 0
    code_extensions = {'.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.go', '.rs', '.c', '.cpp', '.h', '.cs'}

    if file_list:
        # Fast path: reuse discovered file list
        for fpath in file_list:
            ext = os.path.splitext(fpath)[1].lower()
            if ext in code_extensions:
                try:
                    with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                        total_loc += sum(1 for line in f if line.strip())
                except Exception:
                    continue
        return total_loc

    for root, dirs, files in os.walk(workspace):
        # Skip common non-code directories
        dirs[:] = [d for d in dirs if d not in {
            '.git', '.venv', 'venv', 'node_modules', '__pycache__', 
            'legacy', '.idea', '.vscode', 'dist', 'build', 'target'
        }]
        
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in code_extensions:
                try:
                    with open(os.path.join(root, file), 'r', encoding='utf-8', errors='ignore') as f:
                        total_loc += sum(1 for line in f if line.strip())
                except Exception:
                    continue
    
    return total_loc


def auto_select_model(workspace: str, available_models: Optional[List[str]] = None) -> Tuple[str, str]:
    """
    Auto-select the best model based on LOC count.
    
    Returns:
        Tuple of (model_name, reason)
    """
    loc = count_lines_of_code(workspace)
    
    if available_models is None:
        available_models = get_available_ollama_models()
    
    # Filter to audit-suitable models that are available
    available_audit_models = [m for m in available_models if is_model_audit_suitable(m)]
    
    # Determine target tier based on LOC
    if loc < 10000:
        target_tier = ModelTier.SMALL
        tier_reason = f"small codebase ({loc:,} LOC)"
    elif loc < 50000:
        target_tier = ModelTier.MEDIUM
        tier_reason = f"medium codebase ({loc:,} LOC)"
    else:
        target_tier = ModelTier.LARGE
        tier_reason = f"large codebase ({loc:,} LOC)"
    
    # Find best available model for tier
    best_model = None
    for model_name in available_audit_models:
        info = get_model_info(model_name)
        if info and info.tier == target_tier:
            best_model = model_name
            break
    
    # Fallback: any available audit model
    if not best_model and available_audit_models:
        best_model = available_audit_models[0]
        return best_model, f"fallback (recommended tier '{target_tier.value}' not available)"
    
    # Final fallback: default model
    if not best_model:
        return DEFAULT_MODEL, f"default (no audit models found locally, pull with 'ollama pull {DEFAULT_MODEL}')"
    
    return best_model, f"optimal for {tier_reason}"


def validate_model(model_name: str, strict: bool = False) -> Tuple[bool, str]:
    """
    Validate a model for audit suitability.
    
    Args:
        model_name: Name of the model to validate
        strict: If True, reject non-allowlisted models
        
    Returns:
        Tuple of (is_valid, message)
    """
    available = get_available_ollama_models()
    
    # Check if available locally
    model_available = model_name in available or any(
        model_name.split(":")[0] == m.split(":")[0] for m in available
    )
    
    if not model_available:
        return False, f"Model '{model_name}' not found locally. Pull with: ollama pull {model_name}"
    
    # Check if audit-suitable
    if is_model_audit_suitable(model_name):
        info = get_model_info(model_name)
        return True, f"[+] Model '{model_name}' is audit-suitable ({info.tier.value} tier, {info.params_b}B params)"
    
    if strict:
        return False, f"Model '{model_name}' is not in the audit-suitable allowlist. Use --list-models to see recommended models."
    
    return True, f"[!] Model '{model_name}' is not in the allowlist but will be used. Results may vary."


def print_model_list():
    """Print formatted table of available audit models."""
    table = Table(title="DockDesk Audit-Suitable Models", show_header=True, header_style="bold white", border_style="dim")
    
    table.add_column("Model", style="white", no_wrap=True)
    table.add_column("Role", style="white")
    table.add_column("Tier", style="white")
    table.add_column("Params", justify="right")
    table.add_column("LOC Range", justify="right")
    table.add_column("Available", justify="center")
    table.add_column("Description")
    
    available = get_available_ollama_models()
    
    for name, model in sorted(AUDIT_MODELS.items(), key=lambda x: x[1].params_b):
        is_available = name in available or any(name.split(":")[0] == m.split(":")[0] for m in available)
        
        min_loc, max_loc = model.recommended_loc
        loc_range = f"{min_loc//1000}k-{max_loc//1000}k" if max_loc < 1000000 else f"{min_loc//1000}k+"
        
        # Determine role
        if "reasoning" in " ".join(model.strengths).lower() or "chain-of-thought" in " ".join(model.strengths).lower():
            role = "[R] Reasoning"
        else:
            role = "[C] Code"
        
        table.add_row(
            name,
            role,
            model.tier.value.upper(),
            f"{model.params_b}B",
            loc_range,
            "[Y]" if is_available else "[N]",
            model.description[:50] + "..." if len(model.description) > 50 else model.description
        )
    
    console.print(table)
    console.print(f"\n[dim]Default code model:      {DEFAULT_MODEL}[/dim]")
    console.print(f"[dim]Default reasoning model: {DEFAULT_REASONING_MODEL}[/dim]")
    console.print("[dim]Pull a model: ollama pull <model-name>[/dim]")
    console.print("[dim]Auto-select best model: python auditor_slm.py --auto-tune[/dim]")


def get_model_recommendation_message(model_name: str, workspace: str) -> str:
    """Generate a helpful message about model selection."""
    loc = count_lines_of_code(workspace)
    info = get_model_info(model_name)
    
    if not info:
        return f"Using model: {model_name} (not in allowlist)"
    
    min_loc, max_loc = info.recommended_loc
    
    if loc < min_loc:
        return f"[>] Using {model_name} ({info.tier.value}). Consider a smaller model for {loc:,} LOC codebase."
    elif loc > max_loc:
        return f"[>] Using {model_name} ({info.tier.value}). Consider a larger model for {loc:,} LOC codebase."
    else:
        return f"[+] Using {model_name} ({info.tier.value}) - optimal for {loc:,} LOC codebase."
