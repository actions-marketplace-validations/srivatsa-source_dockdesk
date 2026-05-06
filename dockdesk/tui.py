"""
DockDesk TUI v3.0 - Phenomenal interactive terminal dashboard.

4-panel layout with tabs, search, fix integration, accountability view,
ASCII sparklines, and vim-style navigation. Pure rich - no Textual dependency.

Navigation:
  j/↓  Next file        k/↑  Previous file
  g    First file        G    Last file
  /    Search/filter     Esc  Clear filter
  Enter  Expand details  f    Apply fix
  d    Show diff          Tab  Next tab
  1-4  Switch tabs        q    Quit
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text
from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.rule import Rule

console = Console(highlight=False)

# ── Palette ─────────────────────────────────────────────────────────────────
DEEP_PURPLE = "#4B0082"
PURPLE = "#8A2BE2"
ORCHID = "#DA70D6"
MAGENTA = "#FF00FF"
HOT_PINK = "#FF1493"
NEON_PINK = "#FF69B4"
CYBER_YELLOW = "#FFD700"
CYAN_ACCENT = "#00FFFF"
DIM_PURPLE = "#13132B"
BG_DARK = "#0B0B1A"

RISK_COLORS = {"HIGH": "bold red", "MEDIUM": "bold yellow", "LOW": "green", "UNKNOWN": "dim"}
STATUS_ICONS = {"PASS": "", "FAIL": "", "SKIP": "⊘", "ERROR": "", "UNKNOWN": "?"}
RISK_BARS = {"HIGH": "█", "MEDIUM": "▓", "LOW": "░"}

TABS = ["Overview", "Files", "Timeline", "Accountability"]


def _sparkline(values: List[int], width: int = 20) -> str:
    """Generate ASCII sparkline from a list of ints."""
    if not values:
        return "─" * width
    blocks = " ▁▂▃▄▅▆▇█"
    mx = max(values) or 1
    line = ""
    step = max(1, len(values) // width)
    sampled = values[::step][:width]
    for v in sampled:
        idx = min(int((v / mx) * (len(blocks) - 1)), len(blocks) - 1)
        line += blocks[idx]
    return line


def _risk_heatbar(high: int, med: int, low: int, width: int = 20) -> Text:
    """Color-coded risk heatmap bar."""
    total = high + med + low or 1
    h_w = max(1, int(high / total * width)) if high else 0
    m_w = max(1, int(med / total * width)) if med else 0
    l_w = width - h_w - m_w
    bar = Text()
    bar.append("█" * h_w, style="bold red")
    bar.append("█" * m_w, style="bold yellow")
    bar.append("█" * max(l_w, 0), style="green")
    return bar


class TUIDashboard:
    """Interactive terminal dashboard for browsing audit results."""

    def __init__(self, workspace: str):
        self.workspace = workspace
        self.results: List[Dict] = []
        self.filtered: List[Dict] = []
        self.selected_idx = 0
        self.expanded = False
        self.active_tab = 0
        self.filter_text = ""
        self.filtering = False
        self.accountability: Dict = {}
        self.chain_link: Dict = {}
        self.history_runs: List[Dict] = []
        self._load_data()

    def _load_data(self) -> None:
        data_file = os.path.join(self.workspace, "dashboard_data.json")
        if os.path.exists(data_file):
            try:
                with open(data_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.results = data.get("latest_run_files", data.get("latest_results", data.get("results", [])))
                    if not self.results and isinstance(data, list):
                        self.results = data
                    self.accountability = data.get("accountability", {})
                    self.chain_link = data.get("audit_chain_link", {})
                    self.history_runs = data.get("recent_runs", [])
            except Exception:
                pass

        if not self.results:
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

        self.filtered = list(self.results)

    def _apply_filter(self):
        if not self.filter_text:
            self.filtered = list(self.results)
        else:
            ft = self.filter_text.lower()
            self.filtered = [
                r for r in self.results
                if ft in os.path.basename(r.get("file", "")).lower()
                or ft in r.get("risk", "").lower()
                or ft in r.get("status", "").lower()
                or ft in r.get("author", "").lower()
            ]
        self.selected_idx = min(self.selected_idx, max(0, len(self.filtered) - 1))

    # ── Panel Renderers ─────────────────────────────────────────────────

    def _make_stats_header(self) -> Panel:
        total = len(self.results)
        high = sum(1 for r in self.results if r.get("risk") == "HIGH")
        med = sum(1 for r in self.results if r.get("risk") == "MEDIUM")
        low = sum(1 for r in self.results if r.get("risk") == "LOW")
        passed = sum(1 for r in self.results if r.get("status") == "PASS")
        failed = sum(1 for r in self.results if r.get("status") == "FAIL")
        safe = sum(1 for r in self.results if r.get("safe_to_push"))

        line = Text()
        line.append(f"  {total} ", style=f"bold {MAGENTA}")
        line.append("files  ", style=f"dim {ORCHID}")
        line.append(f"{passed} ", style=f"bold {CYAN_ACCENT}")
        line.append(f"{failed} ", style=f"bold {HOT_PINK}")
        line.append("  │  ", style=f"dim {PURPLE}")
        line.append(f"▲{high}", style="bold red")
        line.append(f" ●{med}", style="bold yellow")
        line.append(f" ▼{low}", style="green")
        line.append("  │  ", style=f"dim {PURPLE}")
        line.append(f"{safe} safe  ", style=f"bold {CYAN_ACCENT}")
        line.append("  ", style="")
        line.append(_risk_heatbar(high, med, low, 16))
        line.append("  ", style="")

        # Sparkline from history
        if self.history_runs:
            vals = [r.get("fail_count", 0) for r in self.history_runs[-20:]]
            line.append("  trend:", style=f"dim {ORCHID}")
            line.append(_sparkline(vals, 12), style=f"bold {HOT_PINK}")

        return Panel(line, border_style=f"dim {PURPLE}", height=3, padding=(0, 1))

    def _make_file_list(self) -> Panel:
        table = Table(box=box.SIMPLE, show_header=True, header_style=f"bold {HOT_PINK}", expand=True, padding=(0, 1))
        table.add_column("", width=2, justify="center")
        table.add_column("File", style=f"{ORCHID}", no_wrap=True, ratio=4)
        table.add_column("Risk", justify="center", width=6)
        table.add_column("St", justify="center", width=3)
        table.add_column("Author", style=f"dim {NEON_PINK}", width=12, no_wrap=True)

        visible_start = max(0, self.selected_idx - 15)
        visible_end = min(len(self.filtered), visible_start + 30)

        for i in range(visible_start, visible_end):
            r = self.filtered[i]
            fname = os.path.basename(r.get("file", "unknown"))
            risk = r.get("risk", "UNKNOWN")
            status = r.get("status", "UNKNOWN")
            author = r.get("author", "")[:12]

            pointer = "▸" if i == self.selected_idx else " "
            p_style = f"bold {MAGENTA}" if i == self.selected_idx else "dim"
            risk_styled = Text(risk[:3], style=RISK_COLORS.get(risk, "dim"))
            s_icon = STATUS_ICONS.get(status, "?")
            s_color = "green" if status == "PASS" else "red" if status == "FAIL" else "dim"
            row_style = f"on {DIM_PURPLE}" if i == self.selected_idx else ""

            table.add_row(
                Text(pointer, style=p_style),
                Text(fname, style=f"bold {MAGENTA}" if i == self.selected_idx else f"{ORCHID}"),
                risk_styled, Text(s_icon, style=s_color), Text(author, style=f"dim {NEON_PINK}"),
                style=row_style,
            )

        title_text = f" Files ({len(self.filtered)}"
        if self.filter_text:
            title_text += f" ∣ /{self.filter_text}"
        title_text += ") "

        return Panel(table, title=Text(title_text, style=f"bold {HOT_PINK}"), border_style=PURPLE, padding=(0, 0))

    def _make_detail_panel(self) -> Panel:
        if not self.filtered:
            return Panel(Text("No results.", style=f"dim {ORCHID}"), title=Text(" Details ", style=f"bold {HOT_PINK}"), border_style=PURPLE)

        r = self.filtered[self.selected_idx]
        lines = []
        lines.append(f"[bold {ORCHID}]File:[/] [{NEON_PINK}]{r.get('file', 'unknown')}[/]")
        lines.append(f"[bold {ORCHID}]Status:[/] [{RISK_COLORS.get(r.get('risk',''), 'dim')}]{r.get('status', '?')}[/]  "
                      f"[bold {ORCHID}]Risk:[/] [{RISK_COLORS.get(r.get('risk',''), 'dim')}]{r.get('risk', '?')}[/]")

        author = r.get("author", "Unknown")
        commit = r.get("last_commit", "")[:12]
        team = r.get("team", "")
        lines.append(f"[bold {ORCHID}]Author:[/] [{NEON_PINK}]{author}[/]  "
                      f"[bold {ORCHID}]Commit:[/] [{NEON_PINK}]{commit}[/]"
                      + (f"  [bold {ORCHID}]Team:[/] [{NEON_PINK}]{team}[/]" if team else ""))

        dur = r.get("duration_ms", 0)
        if dur:
            lines.append(f"[bold {ORCHID}]Duration:[/] [{NEON_PINK}]{dur}ms[/]")

        lines.append("")
        lines.append(f"[bold {HOT_PINK}]Summary[/]")
        lines.append(f"[{NEON_PINK}]{r.get('summary', 'No summary')}[/]")

        if self.expanded:
            reasoning = r.get("reasoning", "")
            fix = r.get("fix", "")
            if reasoning:
                lines.append(f"\n[bold {HOT_PINK}]Reasoning[/]")
                lines.append(f"[dim {ORCHID}]{reasoning[:400]}[/]")
            if fix:
                lines.append(f"\n[bold {HOT_PINK}]Suggested Fix[/]")
                lines.append(f"[dim {ORCHID}]{fix[:400]}[/]")

        exp_tag = "(expanded)" if self.expanded else "(Enter=expand, f=fix, d=diff)"
        return Panel(
            Text.from_markup("\n".join(lines)),
            title=Text(f" Details {exp_tag} ", style=f"bold {HOT_PINK}"),
            border_style=PURPLE, padding=(1, 2),
        )

    def _make_accountability_panel(self) -> Panel:
        devs = self.accountability.get("developers", {})
        if not devs:
            return Panel(Text("No accountability data. Run an audit first.", style=f"dim {ORCHID}"),
                         title=Text(" Accountability ", style=f"bold {HOT_PINK}"), border_style=PURPLE)

        table = Table(box=box.SIMPLE, show_header=True, header_style=f"bold {HOT_PINK}", expand=True)
        table.add_column("Developer", style=f"{ORCHID}", ratio=3)
        table.add_column("Files", justify="center", width=6)
        table.add_column("Pass", justify="center", width=6, style="green")
        table.add_column("Fail", justify="center", width=6, style="red")
        table.add_column("Team", style=f"dim {NEON_PINK}", width=14)

        sorted_devs = sorted(devs.values(), key=lambda d: d.get("files_authored", 0), reverse=True)
        for d in sorted_devs[:20]:
            table.add_row(
                d.get("name", "?"), str(d.get("files_authored", 0)),
                str(d.get("files_passed", 0)), str(d.get("files_failed", 0)),
                d.get("team", "")[:14],
            )

        chain_info = ""
        if self.chain_link:
            ch = self.chain_link.get("chain_hash", "")[:16]
            chain_info = f"  │  Chain: {ch}..."

        return Panel(table, title=Text(f" Accountability ({len(devs)} devs){chain_info} ", style=f"bold {HOT_PINK}"), border_style=PURPLE)

    def _make_timeline_panel(self) -> Panel:
        if not self.history_runs:
            return Panel(Text("No history. Run multiple audits to see trends.", style=f"dim {ORCHID}"),
                         title=Text(" Timeline ", style=f"bold {HOT_PINK}"), border_style=PURPLE)

        table = Table(box=box.SIMPLE, show_header=True, header_style=f"bold {HOT_PINK}", expand=True)
        table.add_column("Date", style=f"dim {ORCHID}", width=12)
        table.add_column("Files", justify="center", width=6)
        table.add_column("Pass", justify="center", width=6, style="green")
        table.add_column("Fail", justify="center", width=6, style="red")
        table.add_column("HIGH", justify="center", width=5, style="bold red")

        for r in self.history_runs[-15:]:
            date = str(r.get("timestamp", ""))[:10]
            risk = r.get("risk_distribution", {})
            table.add_row(date, str(r.get("files_audited", 0)),
                          str(r.get("pass_count", 0)), str(r.get("fail_count", 0)),
                          str(risk.get("HIGH", 0)))

        return Panel(table, title=Text(f" Timeline ({len(self.history_runs)} runs) ", style=f"bold {HOT_PINK}"), border_style=PURPLE)

    def _make_tab_bar(self) -> Text:
        bar = Text()
        for i, tab in enumerate(TABS):
            if i == self.active_tab:
                bar.append(f" {i+1}:{tab} ", style=f"bold {HOT_PINK} on {DIM_PURPLE}")
            else:
                bar.append(f" {i+1}:{tab} ", style=f"dim {ORCHID}")
            bar.append("│", style=f"dim {PURPLE}")
        return bar

    def _make_status_bar(self) -> Text:
        try:
            from dockdesk.rag import HAS_RAG_DEPS
            rag_status = "Enabled" if HAS_RAG_DEPS else "Disabled"
            rag_color = "green" if HAS_RAG_DEPS else "dim red"
        except ImportError:
            rag_status = "Unknown"
            rag_color = "dim"

        bar = Text()
        bar.append("  DockDesk TUI ", style=f"bold {HOT_PINK} on {DIM_PURPLE}")
        bar.append(f"  {Path(self.workspace).name}  ", style=f"dim {ORCHID}")
        bar.append("│ ", style=f"dim {PURPLE}")
        bar.append(f"RAG Status: {rag_status} ", style=f"bold {rag_color}")
        bar.append("│ ", style=f"dim {PURPLE}")
        if self.filtering:
            bar.append(f"/{self.filter_text}█", style=f"bold {CYAN_ACCENT}")
        else:
            bar.append("j/k:nav  /:search  Tab:switch  Enter:expand  f:fix  q:quit", style=f"dim {ORCHID}")
        return bar

    def _make_layout(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="tabs", size=1),
            Layout(name="stats", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=1),
        )

        layout["tabs"].update(self._make_tab_bar())
        layout["stats"].update(self._make_stats_header())
        layout["footer"].update(self._make_status_bar())

        if self.active_tab == 0:  # Overview
            layout["main"].split_row(
                Layout(name="files", ratio=2, minimum_size=30),
                Layout(name="details", ratio=3),
            )
            layout["files"].update(self._make_file_list())
            layout["details"].update(self._make_detail_panel())
        elif self.active_tab == 1:  # Files
            layout["main"].update(self._make_file_list())
        elif self.active_tab == 2:  # Timeline
            layout["main"].update(self._make_timeline_panel())
        elif self.active_tab == 3:  # Accountability
            layout["main"].update(self._make_accountability_panel())

        return layout

    # ── Input & Run Loop ────────────────────────────────────────────────

    def run(self) -> None:
        if not self.results:
            console.print("[yellow]No audit results to display.[/yellow]")
            console.print("[dim]Run 'dockdesk audit' first to generate results.[/dim]")
            return

        console.print(f"[dim]Loading TUI with {len(self.results)} results...[/dim]")

        if os.name == "nt":
            import msvcrt

            def read_key() -> str:
                if msvcrt.kbhit():
                    ch = msvcrt.getch()
                    if ch in (b'\x00', b'\xe0'):
                        ch2 = msvcrt.getch()
                        if ch2 == b'H': return 'up'
                        if ch2 == b'P': return 'down'
                        if ch2 == b'\t': return 'tab'
                        return ''
                    if ch == b'\r': return 'enter'
                    if ch == b'\x1b': return 'esc'
                    if ch == b'\t': return 'tab'
                    try:
                        c = ch.decode('utf-8', errors='ignore')
                    except Exception:
                        return ''
                    return c
                return ''
        else:
            import tty, termios, select

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
                        return 'esc'
                    if ch in ('\r', '\n'): return 'enter'
                    if ch == '\t': return 'tab'
                    return ch
                return ''

        if os.name != "nt":
            _init_tty()

        try:
            with Live(self._make_layout(), console=console, screen=True, refresh_per_second=10) as live:
                while True:
                    key = read_key()
                    if not key:
                        time.sleep(0.05)
                        continue

                    if self.filtering:
                        if key == 'esc' or key == 'enter':
                            self.filtering = False
                        elif key in ('backspace', '\x7f', '\x08'):
                            self.filter_text = self.filter_text[:-1]
                            self._apply_filter()
                        elif len(key) == 1 and key.isprintable():
                            self.filter_text += key
                            self._apply_filter()
                        live.update(self._make_layout())
                        continue

                    if key == 'q':
                        break
                    elif key in ('j', 'down'):
                        self.selected_idx = min(self.selected_idx + 1, max(0, len(self.filtered) - 1))
                    elif key in ('k', 'up'):
                        self.selected_idx = max(self.selected_idx - 1, 0)
                    elif key == 'g':
                        self.selected_idx = 0
                    elif key == 'G':
                        self.selected_idx = max(0, len(self.filtered) - 1)
                    elif key == 'enter':
                        self.expanded = not self.expanded
                    elif key == '/':
                        self.filtering = True
                        self.filter_text = ""
                    elif key == 'esc':
                        self.filter_text = ""
                        self._apply_filter()
                    elif key == 'tab':
                        self.active_tab = (self.active_tab + 1) % len(TABS)
                    elif key in ('1', '2', '3', '4'):
                        self.active_tab = int(key) - 1
                    elif key == 'f':
                        pass  # Fix integration placeholder
                    elif key == 'd':
                        pass  # Diff view placeholder

                    live.update(self._make_layout())
                    time.sleep(0.03)
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
