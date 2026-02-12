"""
DockDesk Auto-Fix System

Applies fixes to documentation and code with validation and backup.
"""

import os
import shutil
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from rich.console import Console

from .utils import Guardrails

console = Console()

BACKUP_DIR = ".dockdesk_backups"


class FixType(str, Enum):
    DOCUMENTATION = "doc"
    CODE = "code"


class FixStatus(str, Enum):
    PENDING = "pending"
    APPLIED = "applied"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class FixResult:
    """Result of a fix operation."""
    file_path: str
    fix_type: FixType
    status: FixStatus
    original_hash: str
    new_hash: Optional[str] = None
    backup_path: Optional[str] = None
    error: Optional[str] = None
    fix_content: str = ""


def create_backup(file_path: str, workspace: str) -> Optional[str]:
    """Create a backup of a file before modification."""
    try:
        backup_dir = Path(workspace) / BACKUP_DIR
        backup_dir.mkdir(exist_ok=True)
        
        # Create timestamped backup
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        rel_path = os.path.relpath(file_path, workspace).replace(os.sep, "_")
        backup_name = f"{timestamp}_{rel_path}"
        backup_path = backup_dir / backup_name
        
        shutil.copy2(file_path, backup_path)
        return str(backup_path)
    except Exception as e:
        console.print(f"[yellow]Warning: Could not create backup for {file_path}: {e}[/yellow]")
        return None


def get_file_hash(file_path: str) -> str:
    """Calculate SHA-256 hash of file content."""
    try:
        with open(file_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception:
        return ""


def detect_fix_type(file_path: str) -> FixType:
    """Detect whether a file is documentation or code."""
    doc_extensions = {'.md', '.rst', '.txt', '.adoc'}
    ext = Path(file_path).suffix.lower()
    
    if ext in doc_extensions:
        return FixType.DOCUMENTATION
    return FixType.CODE


def validate_fix(fix_content: str, file_path: str, fix_type: FixType) -> Tuple[bool, str]:
    """
    Validate a fix before applying.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not fix_content or not fix_content.strip():
        return False, "Fix content is empty"
    
    # For code fixes, validate syntax
    if fix_type == FixType.CODE:
        ext = Path(file_path).suffix.lower()
        
        if ext == '.py':
            if not Guardrails.validate_python_syntax(fix_content):
                return False, "Invalid Python syntax in fix"
        # Add more language validators as needed
    
    # Basic sanity checks
    if len(fix_content) < 10:
        return False, "Fix content suspiciously short"
    
    return True, ""


def apply_fix(
    file_path: str,
    fix_content: str,
    workspace: str,
    allow_code_fixes: bool = False,
    dry_run: bool = False
) -> FixResult:
    """
    Apply a fix to a file.
    
    Args:
        file_path: Path to the file to fix
        fix_content: The fix content to write
        workspace: Workspace root for backup paths
        allow_code_fixes: Whether to allow code file modifications
        dry_run: If True, validate but don't write
        
    Returns:
        FixResult with status and details
    """
    fix_type = detect_fix_type(file_path)
    original_hash = get_file_hash(file_path)
    
    result = FixResult(
        file_path=file_path,
        fix_type=fix_type,
        status=FixStatus.PENDING,
        original_hash=original_hash,
        fix_content=fix_content
    )
    
    # Check if code fixes are allowed
    if fix_type == FixType.CODE and not allow_code_fixes:
        result.status = FixStatus.SKIPPED
        result.error = "Code fixes disabled (use --fix-code to enable)"
        return result
    
    # Validate the fix
    is_valid, error = validate_fix(fix_content, file_path, fix_type)
    if not is_valid:
        result.status = FixStatus.FAILED
        result.error = f"Validation failed: {error}"
        return result
    
    if dry_run:
        result.status = FixStatus.PENDING
        return result
    
    try:
        # Create backup
        backup_path = create_backup(file_path, workspace)
        result.backup_path = backup_path
        
        # Write the fix
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(fix_content)
        
        result.new_hash = get_file_hash(file_path)
        result.status = FixStatus.APPLIED
        
        console.print(f"[green]✓ Applied fix to {file_path}[/green]")
        if backup_path:
            console.print(f"[dim]  Backup: {backup_path}[/dim]")
            
    except Exception as e:
        result.status = FixStatus.FAILED
        result.error = str(e)
        console.print(f"[red]✗ Failed to apply fix to {file_path}: {e}[/red]")
    
    return result


def apply_fixes_batch(
    audit_results: List[Dict],
    workspace: str,
    allow_code_fixes: bool = False,
    dry_run: bool = False,
    interactive: bool = False
) -> List[FixResult]:
    """
    Apply fixes from audit results in batch.
    
    Args:
        audit_results: List of audit result dicts with 'file' and 'fix' keys
        workspace: Workspace root
        allow_code_fixes: Whether to allow code modifications
        dry_run: Validate only, don't write
        interactive: Prompt for each fix
        
    Returns:
        List of FixResult objects
    """
    results = []
    
    for result in audit_results:
        file_path = result.get("file", "")
        fix_content = result.get("fix", "")
        status = result.get("status", "")
        
        # Only apply fixes for FAIL results
        if status != "FAIL" or not fix_content:
            continue
        
        if not os.path.exists(file_path):
            console.print(f"[yellow]Skipping {file_path}: file not found[/yellow]")
            continue
        
        fix_type = detect_fix_type(file_path)
        
        if interactive:
            console.print(f"\n[bold]Fix for {file_path} ({fix_type.value}):[/bold]")
            console.print(fix_content[:500] + "..." if len(fix_content) > 500 else fix_content)
            
            choice = input("\nApply this fix? (y/n/q): ").lower().strip()
            if choice == 'q':
                break
            if choice != 'y':
                results.append(FixResult(
                    file_path=file_path,
                    fix_type=fix_type,
                    status=FixStatus.SKIPPED,
                    original_hash=get_file_hash(file_path),
                    error="User skipped"
                ))
                continue
        
        fix_result = apply_fix(
            file_path=file_path,
            fix_content=fix_content,
            workspace=workspace,
            allow_code_fixes=allow_code_fixes,
            dry_run=dry_run
        )
        results.append(fix_result)
    
    return results


def restore_from_backup(backup_path: str, original_path: str) -> bool:
    """Restore a file from backup."""
    try:
        shutil.copy2(backup_path, original_path)
        console.print(f"[green]✓ Restored {original_path} from backup[/green]")
        return True
    except Exception as e:
        console.print(f"[red]✗ Failed to restore {original_path}: {e}[/red]")
        return False


def list_backups(workspace: str) -> List[Dict]:
    """List all available backups."""
    backup_dir = Path(workspace) / BACKUP_DIR
    if not backup_dir.exists():
        return []
    
    backups = []
    for backup_file in sorted(backup_dir.iterdir(), reverse=True):
        if backup_file.is_file():
            parts = backup_file.name.split("_", 2)
            if len(parts) >= 3:
                timestamp = f"{parts[0]}_{parts[1]}"
                original_name = parts[2]
                backups.append({
                    "backup_path": str(backup_file),
                    "timestamp": timestamp,
                    "original_name": original_name,
                    "size": backup_file.stat().st_size
                })
    
    return backups


def cleanup_old_backups(workspace: str, keep_count: int = 10):
    """Remove old backups, keeping the most recent ones."""
    backups = list_backups(workspace)
    
    if len(backups) <= keep_count:
        return
    
    to_remove = backups[keep_count:]
    for backup in to_remove:
        try:
            os.remove(backup["backup_path"])
        except Exception:
            pass
    
    console.print(f"[dim]Cleaned up {len(to_remove)} old backups[/dim]")
