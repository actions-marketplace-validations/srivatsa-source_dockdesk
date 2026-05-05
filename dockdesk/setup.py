"""
DockDesk Setup - Interactive Ollama installation and model management.

Guides new users through:
  1. Detecting the OS
  2. Checking / installing Ollama
  3. Ensuring the Ollama service is running
  4. Pulling recommended audit models
"""

import os
import sys
import platform
import shutil
import subprocess
import time
import webbrowser
from typing import List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console(highlight=False)

# ── Recommended models ────────────────────────────────────────────────
RECOMMENDED_MODELS: List[Tuple[str, str, str]] = [
    # (model_name, description, approx_size)
    ("gemma:2b", "Intent routing model (optimized for 4GB VRAM)", "~1.6 GB"),
    ("qwen2.5-coder:7b", "Code audit model (recommended default)", "~4.5 GB"),
    ("deepseek-r1:1.5b", "Reasoning model for risk assessment", "~1 GB"),
]

OLLAMA_INSTALL_URL_WINDOWS = "https://ollama.com/download/windows"
OLLAMA_INSTALL_SCRIPT_UNIX = "https://ollama.com/install.sh"
OLLAMA_API = "http://localhost:11434"


# ── Helpers ───────────────────────────────────────────────────────────

def _detect_os() -> str:
    """Return 'windows', 'macos', or 'linux'."""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    if system == "windows":
        return "windows"
    return "linux"


def _prompt_yn(message: str, default: bool = True) -> bool:
    """Prompt user for yes/no, with a default."""
    hint = "Y/n" if default else "y/N"
    try:
        answer = input(f"      → {message} [{hint}]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print()
        return default
    if not answer:
        return default
    return answer in ("y", "yes")


def _check_ollama_installed() -> bool:
    """Return True if the 'ollama' binary is on the PATH."""
    return shutil.which("ollama") is not None


def _check_ollama_running() -> bool:
    """Return True if the Ollama API is reachable on localhost."""
    import requests
    try:
        resp = requests.get(f"{OLLAMA_API}/api/tags", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


def _get_installed_models() -> List[str]:
    """Return list of locally-available model names from ``ollama list``."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return []
        models = []
        for line in result.stdout.strip().splitlines()[1:]:  # skip header
            parts = line.split()
            if parts:
                models.append(parts[0])
        return models
    except Exception:
        return []


def _install_ollama(os_name: str) -> bool:
    """
    Attempt to install Ollama.

    - macOS / Linux: runs the official install script.
    - Windows: opens the download page in the default browser.

    Returns True if the user confirms installation succeeded.
    """
    if os_name == "windows":
        console.print(f"      Opening [bold cyan]{OLLAMA_INSTALL_URL_WINDOWS}[/bold cyan] in your browser …")
        webbrowser.open(OLLAMA_INSTALL_URL_WINDOWS)
        console.print("      [dim]Download and run the installer, then come back here.[/dim]")
        try:
            input("      Press Enter once Ollama is installed … ")
        except (EOFError, KeyboardInterrupt):
            console.print()
        return _check_ollama_installed()
    else:
        console.print(f"      Running: [bold cyan]curl -fsSL {OLLAMA_INSTALL_SCRIPT_UNIX} | sh[/bold cyan]")
        try:
            subprocess.run(
                ["bash", "-c", f"curl -fsSL {OLLAMA_INSTALL_SCRIPT_UNIX} | sh"],
                check=True,
            )
            return _check_ollama_installed()
        except subprocess.CalledProcessError:
            console.print("      [red]✗ Installation script failed.[/red]")
            console.print(f"      Install manually: [bold cyan]{OLLAMA_INSTALL_SCRIPT_UNIX}[/bold cyan]")
            return False


def _start_ollama_service(os_name: str) -> bool:
    """Try to start ``ollama serve`` in the background."""
    try:
        if os_name == "windows":
            # On Windows, start detached
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
            )
        else:
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        # Give it a moment to start
        for _ in range(10):
            time.sleep(1)
            if _check_ollama_running():
                return True
        return False
    except Exception:
        return False


def _pull_model(model_name: str) -> bool:
    """Pull a model via ``ollama pull``. Streams output live."""
    try:
        proc = subprocess.run(
            ["ollama", "pull", model_name],
            timeout=600,  # 10 min max per model
        )
        return proc.returncode == 0
    except subprocess.TimeoutExpired:
        console.print(f"      [red]✗ Timed out pulling {model_name}[/red]")
        return False
    except Exception as exc:
        console.print(f"      [red]✗ Error pulling {model_name}: {exc}[/red]")
        return False


# ── Main orchestration ────────────────────────────────────────────────

def run_setup(
    skip_install: bool = False,
    models: Optional[List[str]] = None,
) -> None:
    """
    Interactive first-run setup.

    Steps:
        1. Detect OS
        2. Check / install Ollama
        3. Ensure Ollama service is running
        4. Pull recommended models
    """
    console.print()
    console.print(Panel.fit(
        "[bold white]DockDesk Setup[/bold white]\n"
        "[dim]Install Ollama & pull recommended models[/dim]",
        border_style="cyan",
    ))
    console.print()

    # ── Step 1: Detect OS ─────────────────────────────────────────────
    os_name = _detect_os()
    os_label = {"windows": "Windows", "macos": "macOS", "linux": "Linux"}[os_name]
    console.print(f"[bold white][1/4] Detecting OS …[/bold white]  {os_label}")

    # ── Step 2: Check / install Ollama ────────────────────────────────
    console.print()
    console.print("[bold white][2/4] Checking Ollama …[/bold white]", end=" ")
    if _check_ollama_installed():
        console.print("[green]Found [/green]")
    elif skip_install:
        console.print("[yellow]Not found (--skip-install)[/yellow]")
        console.print("      Install manually: [bold cyan]https://ollama.com[/bold cyan]")
        return
    else:
        console.print("[yellow]Not found[/yellow]")
        if _prompt_yn("Install Ollama now?"):
            success = _install_ollama(os_name)
            if success:
                console.print("      [green]Ollama installed [/green]")
            else:
                console.print("      [red]✗ Ollama not detected after install.[/red]")
                console.print("      Please install manually and re-run [bold]dockdesk setup[/bold].")
                return
        else:
            console.print("      Skipped. Install Ollama before running audits.")
            console.print("      [dim]https://ollama.com[/dim]")
            return

    # ── Step 3: Ensure service running ────────────────────────────────
    console.print()
    console.print("[bold white][3/4] Checking Ollama service …[/bold white]", end=" ")
    if _check_ollama_running():
        console.print("[green]Running [/green]")
    else:
        console.print("[yellow]Not running[/yellow]")
        console.print("      Starting ollama serve …")
        if _start_ollama_service(os_name):
            console.print("      [green]Service started [/green]")
        else:
            console.print("      [yellow] Could not auto-start Ollama.[/yellow]")
            console.print("      Run [bold cyan]ollama serve[/bold cyan] in another terminal, then re-run setup.")
            return

    # ── Step 4: Pull recommended models ───────────────────────────────
    console.print()
    console.print("[bold white][4/4] Model setup[/bold white]")

    installed = _get_installed_models()

    # Determine which models to pull
    if models:
        to_pull = [(m, "", "") for m in models]
    else:
        to_pull = RECOMMENDED_MODELS

    pulled_any = False
    for model_name, desc, size in to_pull:
        # Check if already installed
        already = model_name in installed or any(
            model_name.split(":")[0] == m.split(":")[0] and model_name.split(":")[-1] == m.split(":")[-1]
            for m in installed
        )
        if already:
            label = f"{model_name}"
            if desc:
                label += f" - {desc}"
            console.print(f"      [green][/green] {label} [dim](already installed)[/dim]")
            continue

        label = f"{model_name}"
        if desc:
            label += f" - {desc}"
        if size:
            label += f" [dim]({size})[/dim]"

        if _prompt_yn(f"Pull {label}?"):
            console.print(f"      Pulling {model_name} …")
            if _pull_model(model_name):
                console.print(f"      [green] {model_name} ready[/green]")
                pulled_any = True
            else:
                console.print(f"      [red]✗ Failed to pull {model_name}[/red]")
                console.print(f"      Try manually: [bold cyan]ollama pull {model_name}[/bold cyan]")
        else:
            console.print(f"      Skipped {model_name}")

    # ── Done ──────────────────────────────────────────────────────────
    console.print()
    console.print(Panel.fit(
        "[bold green] Setup complete![/bold green]\n\n"
        "Run your first audit:\n"
        "  [bold cyan]dockdesk audit --workspace /path/to/project[/bold cyan]\n\n"
        "Or initialize a config file:\n"
        "  [bold cyan]dockdesk init[/bold cyan]",
        border_style="green",
    ))
