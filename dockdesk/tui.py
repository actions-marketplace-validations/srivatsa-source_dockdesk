"""
DockDesk TUI — Lightweight interactive terminal dashboard.

Uses rich.live + rich.layout for a split-screen audit results viewer.
No Textual dependency required — pure rich.

Navigation:
  j/↓  Next file        k/↑  Previous file
  Enter  Expand/collapse details
  q  Quit
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

console = Console(highlight=False)

# ── Palette (reuse from ui.py) ─────────────────────────────────────────────────
DEEP_PURPLE = "#4B0082"
PURPLE = "#8A2BE2"
ORCHID = "#DA70D6"
MAGENTA = "#FF00FF"
HOT_PINK = "#FF1493"
NEON_PINK = "#FF69B4"
CYBER_YELLOW = "#FFD700"
CYAN_ACCENT = "#00FFFF"
DIM_PURPLE = "#3D1A78"

RISK_COLORS = {"HIGH": "bold red", "MEDIUM": "bold yellow", "LOW": "green", "UNKNOWN": "dim"}
STATUS_ICONS = {"PASS": "✔", "FAIL": "✘", "SKIP": "⊘", "ERROR": "⚠", "UNKNOWN": "?"}


class TUIDashboard:
    """Interactive terminal dashboard for browsing audit results."""

    def __init__(self, workspace: str):
        self.workspace = workspace
        self.results: List[Dict] = []
        self.selected_idx = 0
        self.expanded = False
        self._load_data()

    def _load_data(self) -> None:
        """Load audit data from dashboard_data.json or audit_history.jsonl."""
        # Try dashboard export first
        data_file = os.path.join(self.workspace, "dashboard_data.json")
        if os.path.exists(data_file):
            try:
                with open(data_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.results = data.get("latest_results", data.get("results", []))
                    if not self.results and isinstance(data, list):
                        self.results = data
                    return
            except Exception:
                pass

        # Fallback: parse audit_history.jsonl
        history_file = os.path.join(self.workspace, "audit_history.jsonl")
        if os.path.exists(history_file):
            try:
                last_run = None
                with open(history_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                            if "run_metadata" in entry:
                                last_run = entry
                        except json.JSONDecodeError:
                            continue
                if last_run:
                    self.results = last_run.get("results", [])
            except Exception:
                pass

    def _make_file_list(self) -> Panel:
        """Render the left panel: file list with status indicators."""
        table = Table(
            box=box.SIMPLE,
            show_header=True,
            header_style=f"bold {HOT_PINK}",
            expand=True,
            padding=(0, 1),
        )
        table.add_column("", width=3, justify="center")
        table.add_column("File", style=f"{ORCHID}", no_wrap=True, ratio=4)
        table.add_column("Risk", justify="center", width=8)
        table.add_column("St", justify="center", width=3)

        for i, r in enumerate(self.results):
            fname = os.path.basename(r.get("file", "unknown"))
            risk = r.get("risk", "UNKNOWN")
            status = r.get("status", "UNKNOWN")

            # Selection indicator
            pointer = "▸" if i == self.selected_idx else " "
            pointer_style = f"bold {MAGENTA}" if i == self.selected_idx else "dim"

            risk_styled = Text(risk, style=RISK_COLORS.get(risk, "dim"))
            status_icon = STATUS_ICONS.get(status, "?")
            status_color = "green" if status == "PASS" else "red" if status == "FAIL" else "dim"

            row_style = f"on {DIM_PURPLE}" if i == self.selected_idx else ""

            table.add_row(
                Text(pointer, style=pointer_style),
                Text(fname, style=f"{ORCHID}" if i != self.selected_idx else f"bold {MAGENTA}"),
                risk_styled,
                Text(status_icon, style=status_color),
                style=row_style,
            )

        return Panel(
            table,
            title=Text(f" Files ({len(self.results)}) ", style=f"bold {HOT_PINK}"),
            border_style=PURPLE,
            padding=(0, 0),
        )

    def _make_detail_panel(self) -> Panel:
        """Render the right panel: details for the selected file."""
        if not self.results:
            return Panel(
                Text("No audit results loaded.", style=f"dim {ORCHID}"),
                title=Text(" Details ", style=f"bold {HOT_PINK}"),
                border_style=PURPLE,
            )

        r = self.results[self.selected_idx]
        file_path = r.get("file", "unknown")
        status = r.get("status", "UNKNOWN")
        risk = r.get("risk", "UNKNOWN")
        summary = r.get("summary", "No summary available")
        fix = r.get("fix", "")
        reasoning = r.get("reasoning", "")
        findings = r.get("findings", [])
        duration = r.get("duration_ms", 0)

        lines = []
        lines.append(f"[bold {ORCHID}]File:[/bold {ORCHID}] [{NEON_PINK}]{file_path}[/{NEON_PINK}]")
        lines.append(f"[bold {ORCHID}]Status:[/bold {ORCHID}] [{RISK_COLORS.get(risk, 'dim')}]{status}[/{RISK_COLORS.get(risk, 'dim')}]")
        lines.append(f"[bold {ORCHID}]Risk:[/bold {ORCHID}] [{RISK_COLORS.get(risk, 'dim')}]{risk}[/{RISK_COLORS.get(risk, 'dim')}]")
        if duration:
            lines.append(f"[bold {ORCHID}]Duration:[/bold {ORCHID}] [{NEON_PINK}]{duration}ms[/{NEON_PINK}]")
        lines.append("")
        lines.append(f"[bold {HOT_PINK}]Summary[/bold {HOT_PINK}]")
        lines.append(f"[{NEON_PINK}]{summary}[/{NEON_PINK}]")

        if findings:
            lines.append("")
            lines.append(f"[bold {HOT_PINK}]Findings[/bold {HOT_PINK}]")
            for f_item in findings[:10]:
                lines.append(f"  [dim {ORCHID}]•[/dim {ORCHID}] [{NEON_PINK}]{f_item}[/{NEON_PINK}]")

        if self.expanded:
            if reasoning:
                lines.append("")
                lines.append(f"[bold {HOT_PINK}]Reasoning[/bold {HOT_PINK}]")
                lines.append(f"[dim {ORCHID}]{reasoning[:500]}[/dim {ORCHID}]")
            if fix:
                lines.append("")
                lines.append(f"[bold {HOT_PINK}]Suggested Fix[/bold {HOT_PINK}]")
                lines.append(f"[dim {ORCHID}]{fix[:500]}[/dim {ORCHID}]")

        content = "\n".join(lines)

        return Panel(
            Text.from_markup(content),
            title=Text(f" Details {'(expanded)' if self.expanded else '(Enter to expand)'} ", style=f"bold {HOT_PINK}"),
            border_style=PURPLE,
            padding=(1, 2),
        )

    def _make_status_bar(self) -> Text:
        """Render the bottom status bar."""
        total = len(self.results)
        high = sum(1 for r in self.results if r.get("risk") == "HIGH")
        med = sum(1 for r in self.results if r.get("risk") == "MEDIUM")
        low = sum(1 for r in self.results if r.get("risk") == "LOW")
        passed = sum(1 for r in self.results if r.get("status") == "PASS")

        bar = Text()
        bar.append(" ◈ DockDesk TUI ", style=f"bold {HOT_PINK} on {DIM_PURPLE}")
        bar.append(f"  {total} files  ", style=f"dim {ORCHID}")
        bar.append(f"▲{high}", style="bold red")
        bar.append(f" ●{med}", style="bold yellow")
        bar.append(f" ▼{low}", style="green")
        bar.append(f" ✔{passed}", style=CYAN_ACCENT)
        bar.append("  │  ", style=f"dim {PURPLE}")
        bar.append("j/k:navigate  Enter:expand  q:quit", style=f"dim {ORCHID}")
        return bar

    def _make_layout(self) -> Layout:
        """Build the full TUI layout."""
        layout = Layout()
        layout.split_column(
            Layout(name="main", ratio=1),
            Layout(name="footer", size=1),
        )
        layout["main"].split_row(
            Layout(name="files", ratio=2, minimum_size=30),
            Layout(name="details", ratio=3),
        )
        layout["files"].update(self._make_file_list())
        layout["details"].update(self._make_detail_panel())
        layout["footer"].update(self._make_status_bar())
        return layout

    def run(self) -> None:
        """Run the interactive TUI loop."""
        if not self.results:
            console.print("[yellow]No audit results to display.[/yellow]")
            console.print("[dim]Run 'dockdesk audit' first to generate results.[/dim]")
            return

        console.print(f"[dim]Loading TUI with {len(self.results)} results...[/dim]")

        # Platform-specific key reading
        if os.name == "nt":
            import msvcrt

            def read_key() -> str:
                if msvcrt.kbhit():
                    ch = msvcrt.getch()
                    if ch in (b'\x00', b'\xe0'):
                        ch2 = msvcrt.getch()
                        if ch2 == b'H': return 'up'
                        if ch2 == b'P': return 'down'
                        return ''
                    if ch == b'\r': return 'enter'
                    if ch == b'q': return 'q'
                    if ch == b'j': return 'down'
                    if ch == b'k': return 'up'
                return ''
        else:
            import tty
            import termios
            import select

            _old_settings = None

            def _init_tty():
                nonlocal _old_settings
                _old_settings = termios.tcgetattr(sys.stdin)
                tty.setcbreak(sys.stdin.fileno())

            def _restore_tty():
                if _old_settings:
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, _old_settings)

            def read_key() -> str:
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    ch = sys.stdin.read(1)
                    if ch == '\x1b':
                        ch2 = sys.stdin.read(1)
                        ch3 = sys.stdin.read(1)
                        if ch3 == 'A': return 'up'
                        if ch3 == 'B': return 'down'
                        return ''
                    if ch == '\r' or ch == '\n': return 'enter'
                    if ch == 'q': return 'q'
                    if ch == 'j': return 'down'
                    if ch == 'k': return 'up'
                return ''

        # Set up terminal for Unix
        if os.name != "nt":
            _init_tty()

        import time
        try:
            with Live(self._make_layout(), console=console, screen=True, refresh_per_second=10) as live:
                while True:
                    key = read_key()
                    if key == 'q':
                        break
                    elif key == 'down':
                        self.selected_idx = min(self.selected_idx + 1, len(self.results) - 1)
                    elif key == 'up':
                        self.selected_idx = max(self.selected_idx - 1, 0)
                    elif key == 'enter':
                        self.expanded = not self.expanded

                    live.update(self._make_layout())
                    time.sleep(0.05)
        except KeyboardInterrupt:
            pass
        finally:
            if os.name != "nt":
                _restore_tty()

        console.print("[dim]TUI closed.[/dim]")


def launch_tui(workspace: str) -> None:
    """Entry point: create and run the TUI dashboard."""
    tui = TUIDashboard(workspace)
    tui.run()
