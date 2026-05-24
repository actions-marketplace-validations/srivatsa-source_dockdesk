import time
import random
from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from rich.progress import (
    Progress, BarColumn, TextColumn,
    TimeElapsedColumn, TaskProgressColumn
)
from rich.align import Align
from rich.columns import Columns
from rich.rule import Rule
from rich.padding import Padding
from rich import box

from dockdesk import __version__ as _PKG_VERSION

console = Console(highlight=False)

# ── Palette ────────────────────────────────────────────────────────────────────
DEEP_PURPLE   = "#4B0082"
PURPLE        = "#8A2BE2"
VIOLET        = "#9400D3"
ORCHID        = "#DA70D6"
MAGENTA       = "#FF00FF"
HOT_PINK      = "#FF1493"
NEON_PINK     = "#FF69B4"
CYBER_YELLOW  = "#FFD700"
CYAN_ACCENT   = "#00FFFF"
DIM_PURPLE    = "#3D1A78"


ASCII_LOGO = r"""
██████╗  ██████╗  ██████╗██╗  ██╗██████╗ ███████╗███████╗██╗  ██╗
██╔══██╗██╔═══██╗██╔════╝██║ ██╔╝██╔══██╗██╔════╝██╔════╝██║ ██╔╝
██║  ██║██║   ██║██║     █████╔╝ ██║  ██║█████╗  ███████╗█████╔╝ 
██║  ██║██║   ██║██║     ██╔═██╗ ██║  ██║██╔══╝  ╚════██║██╔═██╗ 
██████╔╝╚██████╔╝╚██████╗██║  ██╗██████╔╝███████╗███████║██║  ██╗
╚═════╝  ╚═════╝  ╚═════╝╚═╝  ╚═╝╚═════╝ ╚══════╝╚══════╝╚═╝  ╚═╝
"""

GRADIENT_COLORS = [
    "#4B0082", "#5C0099", "#6A00B0", "#7800C8",
    "#8A2BE2", "#9B1FDE", "#AC13D9", "#BD08D4",
    "#CC00CC", "#D900B8", "#E600A3", "#F2008F",
    "#FF007A", "#FF0066", "#FF1493",
]


def print_logo(version: str = "", animated: bool = True):
    if not version:
        version = _PKG_VERSION
    lines = ASCII_LOGO.strip("\n").split("\n")
    total_lines = len(lines)
    for i, line in enumerate(lines):
        color_idx = int((i / max(total_lines - 1, 1)) * (len(GRADIENT_COLORS) - 1))
        color = GRADIENT_COLORS[color_idx]
        t = Text(line, style=f"bold {color}")
        console.print(Align.center(t))
        if animated:
            time.sleep(0.045)

    tagline = Text()
    tagline.append("    ", style=f"bold {PURPLE}")
    tagline.append("Semantic Code & Documentation Auditor", style=f"bold {ORCHID}")
    tagline.append("    ", style=f"bold {PURPLE}")
    console.print(Align.center(tagline))
    console.print(Align.center(Text(f"v{version}  ·  Neural Edition", style=f"dim {MAGENTA}")))
    console.print()

def print_init_spinners(skip: bool = False, version: str = "", init_steps=None):
    if not version:
        version = _PKG_VERSION
    if not skip:
        print_logo(version, animated=True)
    else:
        # Just minimal banner if skipped
        print_logo(version, animated=False)
        return

    if init_steps is None:
        init_steps = [
            ("dots", "Initializing neural auditor", 0.9),
            ("dots2", "Loading code analysis engine", 1.1),
            ("dots3", "Connecting to local LLM backend", 1.4),
        ]

    for spinner, label, duration in init_steps:
        with console.status(
            Text(f"  {label}…", style=f"bold {MAGENTA}"),
            spinner=spinner,
            spinner_style=f"bold {HOT_PINK}",
        ):
            time.sleep(duration)

        tick = Text()
        tick.append("    ", style=f"bold {HOT_PINK}")
        tick.append(label, style=f"{ORCHID}")
        console.print(tick)
        time.sleep(0.08)

    console.print()
    badge = Text()
    badge.append("  SYSTEM READY  ", style=f"bold {HOT_PINK} on {DIM_PURPLE}")
    console.print(Align.center(badge))
    console.print()
    time.sleep(0.5)

def print_config_panel(workspace, models, loc, exec_mode, out_format, risk_thres):
    table = Table.grid(padding=(0, 2))
    table.add_column(style=f"bold {ORCHID}", justify="right")
    table.add_column(style=f"bold {MAGENTA}")

    rows = [
        ("WORKSPACE",      str(workspace)),
        ("MODELS",         str(models)),
        ("LINES OF CODE",  str(loc)),
        ("EXEC MODE",      str(exec_mode)),
        ("OUTPUT FORMAT",  str(out_format)),
        ("RISK THRESHOLD", str(risk_thres)),
    ]

    for key, val in rows:
        table.add_row(f" {key}", val)

    panel = Panel(
        Padding(table, (1, 2)),
        title=Text("[ MISSION CONFIGURATION ]", style=f"bold {HOT_PINK}"),
        border_style=f"bold {PURPLE}",
        box=box.DOUBLE_EDGE,
        padding=(0, 1),
    )
    console.print(panel)
    console.print()

def get_progress_bar():
    return Progress(
        TextColumn(f"[bold {MAGENTA}][progress.description]{{task.description}}[/]"),
        BarColumn(
            bar_width=32,
            style=DEEP_PURPLE,
            complete_style=HOT_PINK,
            finished_style=MAGENTA,
            pulse_style=ORCHID,
        ),
        TaskProgressColumn(style=f"bold {ORCHID}"),
        TextColumn(f"[bold {PURPLE}]·[/]"),
        TextColumn("{task.fields[filename]}", style=f"dim {ORCHID}"),
        TimeElapsedColumn(),
        console=console,
        expand=True,
        transient=True,
        refresh_per_second=8,
        redirect_stdout=True,
        redirect_stderr=True,
    )

def print_section_rule(text: str):
    console.print(
        Rule(Text(f"    {text}    ", style=f"bold {HOT_PINK}"), style=PURPLE)
    )
    console.print()

def get_results_table():
    table = Table(
        box=box.HEAVY_HEAD,
        border_style=PURPLE,
        header_style=f"bold {HOT_PINK}",
        show_lines=True,
        expand=True,
        title=Text("DockDesk Semantic Audit Report", style=f"bold {MAGENTA}"),
        title_justify="center",
    )
    table.add_column("FILE",    style=f"bold {ORCHID}", no_wrap=False, ratio=3)
    table.add_column("STATUS",  justify="center",        ratio=1)
    table.add_column("RISK",    justify="center",        ratio=1)
    table.add_column("PUSH?",   justify="center",        ratio=1)
    table.add_column("SUMMARY", style=f"dim {NEON_PINK}", ratio=5)
    return table

def print_summary_card(total, pass_count, fail_count, high, med, low, report_path, version=""):
    if not version:
        version = _PKG_VERSION
    grid = Table.grid(padding=(0, 4))
    grid.add_column(justify="center")
    grid.add_column(justify="center")
    grid.add_column(justify="center")
    grid.add_column(justify="center")

    def stat(label, value, color):
        t = Text(justify="center")
        t.append(f"{value}\n", style=f"bold {color}")
        t.append(label, style=f"dim {ORCHID}")
        return t

    flagged = fail_count
    warnings = sum([1 if high == 0 and med > 0 else 0]) # rough approx, will tweak
    
    grid.add_row(
        stat("TOTAL FILES",   str(total),  MAGENTA),
        stat("FAIL / HIGH",   f"{fail_count} / {high}",   HOT_PINK),
        stat("MED / LOW",     f"{med} / {low}",   CYBER_YELLOW),
        stat("PASSED",        str(pass_count),   CYAN_ACCENT),
    )

    verdict = Text(justify="center")
    if high > 0:
        verdict.append("\n    PUSH BLOCKED  ", style=f"bold {HOT_PINK} on {DIM_PURPLE}")
        verdict.append("\n\n", style="")
        verdict.append(f"{high} HIGH-risk file(s) must be resolved.\n", style=f"bold {ORCHID}")
    elif med > 0:
        verdict.append("\n  !  REVIEW NEEDED  ", style=f"bold {CYBER_YELLOW} on {DIM_PURPLE}")
        verdict.append("\n\n", style="")
        verdict.append(f"{med} MEDIUM-risk file(s) found.\n", style=f"bold {ORCHID}")
    else:
        verdict.append("\n    PUSH SAFE  ", style=f"bold {CYAN_ACCENT} on {DIM_PURPLE}")
        verdict.append("\n\n", style="")
        verdict.append(f"All files passed.\n", style=f"bold {ORCHID}")
        
    verdict.append("Run ", style=f"dim {NEON_PINK}")
    verdict.append("dockdesk audit --fix", style=f"bold {MAGENTA}")
    verdict.append(" to apply suggested patches.\n", style=f"dim {NEON_PINK}")
    verdict.append(f"Report: {report_path}", style=f"dim {PURPLE}")

    summary_content = Table.grid(padding=(1, 0))
    summary_content.add_row(Align.center(grid))
    summary_content.add_row(Align.center(verdict))

    panel = Panel(
        summary_content,
        title=Text("[ MISSION DEBRIEF ]", style=f"bold {HOT_PINK}"),
        subtitle=Text(f"DockDesk v{version}  ·  Neural Edition", style=f"dim {PURPLE}"),
        border_style=f"bold {HOT_PINK}" if high > 0 else f"bold {CYBER_YELLOW}" if med > 0 else f"bold {CYAN_ACCENT}",
        box=box.DOUBLE_EDGE,
        padding=(1, 4),
    )
    console.print(Align.center(panel))
    console.print()

    # Footer rule
    console.print(
        Rule(Text("  end of session  ", style=f"dim {PURPLE}"), style=DIM_PURPLE)
    )
    console.print(
        Align.center(Text("  DockDesk    all rights reserved  ",
                          style=f"dim {DIM_PURPLE}"))
    )
    console.print()


# ── Live Thinking Panel ────────────────────────────────────────────────────────

class ThinkingPanel:
    """Context manager that shows a live-updating panel of LLM reasoning tokens.

    Usage:
        with ThinkingPanel("reasoning_node") as panel:
            for token in stream:
                panel.update(token)
    """

    def __init__(self, label: str = "Agent is Thinking", max_lines: int = 12):
        from rich.live import Live
        self._label = label
        self._max_lines = max_lines
        self._tokens: list[str] = []
        self._live: Live | None = None
        self._text = ""

    def _render(self) -> Panel:
        # Show the last N lines of accumulated reasoning
        lines = self._text.split("\n")
        visible = lines[-self._max_lines:]  if len(lines) > self._max_lines else lines
        display = "\n".join(visible)
        if len(lines) > self._max_lines:
            display = f"[dim]... ({len(lines) - self._max_lines} lines hidden)[/dim]\n" + display

        return Panel(
            Text.from_markup(f"[dim {ORCHID}]{display}[/dim {ORCHID}]") if display else Text("waiting for tokens...", style=f"dim {ORCHID}"),
            title=Text(f"  {self._label}  ", style=f"bold {HOT_PINK}"),
            border_style=f"dim {PURPLE}",
            padding=(0, 2),
            width=min(console.width, 100),
        )

    def __enter__(self) -> "ThinkingPanel":
        from rich.live import Live
        self._live = Live(self._render(), console=console, refresh_per_second=6, transient=True)
        self._live.__enter__()
        return self

    def __exit__(self, *args) -> None:
        if self._live:
            self._live.__exit__(*args)
        # Print a compact summary line after the live panel closes
        char_count = len(self._text)
        line_count = self._text.count("\n") + 1
        t = Text()
        t.append("  ", style=f"bold {HOT_PINK}")
        t.append(f"Reasoning complete ", style=f"{ORCHID}")
        t.append(f"({line_count} lines, {char_count} chars)", style=f"dim {PURPLE}")
        console.print(t)

    def update(self, token: str) -> None:
        """Append a token and refresh the live display."""
        self._text += token
        if self._live:
            self._live.update(self._render())

    def set_text(self, full_text: str) -> None:
        """Replace the entire buffer (used for non-streaming mode)."""
        self._text = full_text
        if self._live:
            self._live.update(self._render())

