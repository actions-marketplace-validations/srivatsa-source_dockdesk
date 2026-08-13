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
        
        console.print(f"[green] Applied fix to {file_path}[/green]")
        if backup_path:
            console.print(f"[dim]  Backup: {backup_path}[/dim]")
            
    except Exception as e:
        result.status = FixStatus.FAILED
        result.error = str(e)
        console.print(f"[red]✗ Failed to apply fix to {file_path}: {e}[/red]")
    
    return result


def _show_diff(file_path: str, fix_content: str) -> None:
    """Show a side-by-side diff of original vs proposed fix."""
    from rich.syntax import Syntax
    from rich.columns import Columns
    from rich.panel import Panel as RPanel

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            original = f.read()
    except Exception:
        original = "(could not read original)"

    ext = Path(file_path).suffix.lstrip(".")
    lang = ext if ext in ("py", "js", "ts", "go", "rs", "java", "md", "yml") else "text"

    # Truncate for display
    orig_display = original[:2000] + ("\n..." if len(original) > 2000 else "")
    fix_display = fix_content[:2000] + ("\n..." if len(fix_content) > 2000 else "")

    left = RPanel(
        Syntax(orig_display, lang, theme="monokai", line_numbers=True, word_wrap=True),
        title="[bold red]Original[/bold red]",
        border_style="red",
        width=60,
    )
    right = RPanel(
        Syntax(fix_display, lang, theme="monokai", line_numbers=True, word_wrap=True),
        title="[bold green]Proposed Fix[/bold green]",
        border_style="green",
        width=60,
    )
    console.print(Columns([left, right], padding=1))


def _open_in_editor(file_path: str, fix_content: str) -> str:
    """Open fix content in $EDITOR for manual tweaking, return edited content."""
    import tempfile

    editor = os.environ.get("EDITOR", os.environ.get("VISUAL", ""))
    if not editor:
        # Platform-specific fallback
        if os.name == "nt":
            editor = "notepad"
        else:
            editor = "nano"

    ext = Path(file_path).suffix
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=ext, prefix="dockdesk_fix_", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(fix_content)
        tmp_path = tmp.name

    try:
        import subprocess
        subprocess.run([editor, tmp_path], check=True)
        with open(tmp_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        console.print(f"[red]Editor failed: {e}[/red]")
        return fix_content
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _interactive_fix_prompt(file_path: str, fix_content: str, fix_type: FixType) -> str:
    """Show rich interactive fix prompt. Returns: 'y', 'n', 'q', or edited content."""
    from rich.panel import Panel as RPanel

    # Show a compact summary
    console.print()
    console.print(RPanel(
        f"[bold #DA70D6]File:[/bold #DA70D6] [#FF69B4]{file_path}[/#FF69B4]\n"
        f"[bold #DA70D6]Type:[/bold #DA70D6] [#FF69B4]{fix_type.value}[/#FF69B4]\n"
        f"[bold #DA70D6]Size:[/bold #DA70D6] [#FF69B4]{len(fix_content)} chars[/#FF69B4]",
        title="[bold #FF1493]Proposed Fix[/bold #FF1493]",
        border_style="#8A2BE2",
    ))

    # Show first 500 chars preview
    preview = fix_content[:500]
    if len(fix_content) > 500:
        preview += "\n..."
    console.print(f"[dim]{preview}[/dim]")

    while True:
        choice = input("\n  Apply? [y]es  [n]o  [e]dit  [d]iff  [q]uit  [?]help → ").strip().lower()

        if choice in ("y", "yes"):
            return "y"
        elif choice in ("n", "no"):
            return "n"
        elif choice in ("q", "quit"):
            return "q"
        elif choice in ("d", "diff"):
            _show_diff(file_path, fix_content)
        elif choice in ("e", "edit"):
            edited = _open_in_editor(file_path, fix_content)
            console.print(f"[green] Edited fix ({len(edited)} chars)[/green]")
            return edited  # Return the edited content to apply
        elif choice == "?":
            console.print(
                "\n  [bold #FF1493]Fix Options:[/bold #FF1493]\n"
                "    [#DA70D6]y[/#DA70D6]  Apply this fix as-is\n"
                "    [#DA70D6]n[/#DA70D6]  Skip this fix\n"
                "    [#DA70D6]e[/#DA70D6]  Open in $EDITOR for manual tweaking\n"
                "    [#DA70D6]d[/#DA70D6]  Show side-by-side diff (original vs fix)\n"
                "    [#DA70D6]q[/#DA70D6]  Quit fixing (skip all remaining)\n"
                "    [#DA70D6]?[/#DA70D6]  Show this help\n"
            )
        else:
            console.print("[yellow]  Invalid choice. Type '?' for help.[/yellow]")


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
        interactive: Prompt for each fix with rich UI
        
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
            decision = _interactive_fix_prompt(file_path, fix_content, fix_type)

            if decision == 'q':
                break
            if decision == 'n':
                results.append(FixResult(
                    file_path=file_path,
                    fix_type=fix_type,
                    status=FixStatus.SKIPPED,
                    original_hash=get_file_hash(file_path),
                    error="User skipped"
                ))
                continue
            # If decision is a string longer than 1 char, it's edited content
            if len(decision) > 1:
                fix_content = decision
            # else decision == 'y', proceed with original fix_content
        
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
        console.print(f"[green] Restored {original_path} from backup[/green]")
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
