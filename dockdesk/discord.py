"""
DockDesk Discord Webhook Integration

Posts audit summaries, push-guard notifications, and reasoning verdicts
to a Discord channel via webhook. Zero-infrastructure - just an HTTP POST.

All methods are no-ops when no webhook URL is configured.
Failures log warnings but never crash the pipeline.
"""

import os
import time
import asyncio
import sys
from typing import Any, Dict, List, Optional
from rich.console import Console

console = Console()


class DiscordNotifier:
    """Sends formatted embeds to a Discord webhook."""

    MAX_EMBED_DESC = 4000   # Discord embed description limit
    MAX_FIELD_VALUE = 1024  # Discord embed field limit

    def __init__(self, webhook_url: str = ""):
        self.webhook_url = webhook_url or os.environ.get("DOCKDESK_DISCORD_WEBHOOK", "")

    @property
    def enabled(self) -> bool:
        return bool(self.webhook_url)

    # ── Public API ──────────────────────────────────────────────────────

    def post_audit_summary(
        self,
        audit_results: List[Dict],
        run_metadata: Optional[Dict] = None,
        code_model: str = "",
        reasoning_model: str = "",
    ) -> bool:
        """Post a colour-coded audit summary embed to Discord."""
        if not self.enabled:
            return False

        high = sum(1 for r in audit_results if r.get("risk") == "HIGH")
        medium = sum(1 for r in audit_results if r.get("risk") == "MEDIUM")
        low = sum(1 for r in audit_results if r.get("risk") == "LOW")
        passes = sum(1 for r in audit_results if r.get("status") == "PASS")
        fails = sum(1 for r in audit_results if r.get("status") == "FAIL")
        errors = sum(1 for r in audit_results if r.get("status") == "ERROR")

        # Colour: red if HIGH, yellow if MEDIUM, green otherwise
        if high > 0:
            colour = 0xED4245   # red
            title = "\U0001f6a8 DockDesk Audit - HIGH Risk Detected"
        elif medium > 0:
            colour = 0xFEE75C   # yellow
            title = "\u26a0\ufe0f DockDesk Audit - Medium Risk"
        else:
            colour = 0x57F287   # green
            title = "\u2705 DockDesk Audit - All Clear"

        # Model display
        model_line = ""
        if code_model and reasoning_model and code_model != reasoning_model:
            model_line = f"\U0001f9e0 **Code:** `{code_model}` | **Reasoning:** `{reasoning_model}`"
        elif code_model:
            model_line = f"\U0001f916 Model: `{code_model}`"

        # Build per-file table (truncated)
        file_lines: List[str] = []
        for r in audit_results[:25]:  # cap at 25 files
            icon = {"PASS": "\u2705", "FAIL": "\u274c", "ERROR": "\u26a0\ufe0f"}.get(r.get("status", ""), "\u2753")
            risk_icon = {
                "HIGH": "\U0001f534", "MEDIUM": "\U0001f7e1", "LOW": "\U0001f7e2"
            }.get(r.get("risk", ""), "\u26aa")
            fname = os.path.basename(r.get("file", "unknown"))
            safe = r.get("safe_to_push", None)
            safe_tag = ""
            if safe is True:
                safe_tag = " \u2714\ufe0f safe"
            elif safe is False:
                safe_tag = " \u274c unsafe"
            file_lines.append(f"{icon} {risk_icon} `{fname}`{safe_tag}")

        if len(audit_results) > 25:
            file_lines.append(f"... and {len(audit_results) - 25} more")

        files_text = "\n".join(file_lines) or "No files audited."

        # Truncate if needed
        if len(files_text) > self.MAX_FIELD_VALUE:
            files_text = files_text[: self.MAX_FIELD_VALUE - 20] + "\n... (truncated)"

        embed: Dict[str, Any] = {
            "title": title,
            "color": colour,
            "fields": [
                {"name": "Summary", "value": f"\u2705 {passes} Pass | \u274c {fails} Fail | \u26a0\ufe0f {errors} Error", "inline": True},
                {"name": "Risk", "value": f"\U0001f534 {high} HIGH | \U0001f7e1 {medium} MED | \U0001f7e2 {low} LOW", "inline": True},
                {"name": "Files", "value": files_text, "inline": False},
            ],
            "footer": {"text": "DockDesk Neural Auditor"},
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        if model_line:
            embed["description"] = model_line

        return self._send({"embeds": [embed]})

    def post_push_blocked(self, reason: str, audit_results: Optional[List[Dict]] = None) -> bool:
        """Post a red embed when pre-push hook blocks a push."""
        if not self.enabled:
            return False

        high = sum(1 for r in (audit_results or []) if r.get("risk") == "HIGH")
        unsafe = sum(1 for r in (audit_results or []) if r.get("safe_to_push") is False)

        embed: Dict[str, Any] = {
            "title": "\U0001f6d1 Push BLOCKED by DockDesk",
            "color": 0xED4245,
            "description": reason,
            "fields": [],
            "footer": {"text": "DockDesk Pre-Push Guard"},
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        if high:
            embed["fields"].append({"name": "HIGH risk files", "value": str(high), "inline": True})
        if unsafe:
            embed["fields"].append({"name": "Unsafe to push", "value": str(unsafe), "inline": True})

        return self._send({"embeds": [embed]})

    def post_push_approved(self, summary: str = "") -> bool:
        """Post a green embed when push passes audit."""
        if not self.enabled:
            return False

        embed: Dict[str, Any] = {
            "title": "\u2705 Push Approved by DockDesk",
            "color": 0x57F287,
            "description": summary or "Audit passed - no HIGH risk findings.",
            "footer": {"text": "DockDesk Pre-Push Guard"},
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        return self._send({"embeds": [embed]})

    def post_tree_summary(self, audit_results: List[Dict], max_lines: int = 20) -> bool:
        """Post a compact directory -> file status tree for quick channel scanning."""
        if not self.enabled:
            return False

        tree: Dict[str, List[Dict[str, str]]] = {}
        for r in audit_results:
            rel = str(r.get("file", "unknown")).replace("\\", "/")
            parts = rel.split("/")
            directory = "/".join(parts[:-1]) if len(parts) > 1 else "."
            filename = parts[-1]
            tree.setdefault(directory, []).append({
                "name": filename,
                "status": str(r.get("status", "UNKNOWN")),
                "risk": str(r.get("risk", "UNKNOWN")),
            })

        status_icon = {
            "PASS": "✅",
            "FAIL": "❌",
            "ERROR": "",
            "SKIP": "➖",
            "UNKNOWN": "❔",
        }
        risk_icon = {
            "HIGH": "🔴",
            "MEDIUM": "🟡",
            "LOW": "🟢",
            "UNKNOWN": "⚪",
        }

        lines: List[str] = []
        for directory in sorted(tree.keys()):
            lines.append(f"📁 `{directory}`")
            files = sorted(tree[directory], key=lambda f: (f["status"], f["name"]))
            for f in files:
                s = status_icon.get(f["status"], "❔")
                rk = risk_icon.get(f["risk"], "⚪")
                lines.append(f"  └ {s} {rk} `{f['name']}`")
                if len(lines) >= max_lines:
                    break
            if len(lines) >= max_lines:
                break

        if len(lines) < 1:
            lines = ["No files audited."]

        body = "\n".join(lines)
        if len(body) > self.MAX_EMBED_DESC:
            body = body[: self.MAX_EMBED_DESC - 20] + "\n... (truncated)"

        embed: Dict[str, Any] = {
            "title": "🌲 DockDesk Tree Summary",
            "color": 0x5865F2,
            "description": body,
            "footer": {"text": "DockDesk Discord Tree View"},
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        return self._send({"embeds": [embed]})

    def send_test_ping(self, webhook_url: Optional[str] = None) -> bool:
        """Send a simple test notification. Optionally override webhook URL."""
        target_url = webhook_url or self.webhook_url
        if not target_url:
            return False

        original = self.webhook_url
        self.webhook_url = target_url
        try:
            embed: Dict[str, Any] = {
                "title": " DockDesk Test Ping",
                "color": 0x57F287,
                "description": "Discord webhook is configured and reachable.",
                "fields": [
                    {"name": "Status", "value": "✅ Connected", "inline": True},
                    {"name": "Source", "value": "DockDesk dashboard/CLI", "inline": True},
                ],
                "footer": {"text": "DockDesk Neural Auditor"},
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            return self._send({"embeds": [embed]})
        finally:
            self.webhook_url = original

    # ── Internal ────────────────────────────────────────────────────────

    def _send(self, payload: dict) -> bool:
        """POST JSON payload to the Discord webhook. Never raises."""
        try:
            import requests
            resp = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            if resp.status_code in (200, 204):
                console.print("[dim]Discord notification sent.[/dim]")
                return True
            else:
                console.print(f"[yellow]Discord webhook returned {resp.status_code}[/yellow]")
                return False
        except Exception as e:
            console.print(f"[yellow]Discord notification failed: {e}[/yellow]")
            return False


class DiscordBotService:
    """Discord bot with slash commands for two-way DockDesk interactions."""

    def __init__(
        self,
        workspace: str,
        token: str,
        guild_id: Optional[int] = None,
    ):
        self.workspace = os.path.abspath(workspace)
        self.token = token
        self.guild_id = guild_id

    def _changelog_path(self) -> str:
        return os.path.join(self.workspace, "audit_history.jsonl")

    def _load_reader(self):
        from .changelog import ChangelogReader
        path = self._changelog_path()
        if not os.path.exists(path):
            return None
        return ChangelogReader(path)

    def _latest_run_summary(self) -> Dict[str, Any]:
        reader = self._load_reader()
        if not reader:
            return {}
        runs = reader.get_runs(limit=1)
        return runs[0] if runs else {}

    def _stats_summary(self) -> Dict[str, Any]:
        reader = self._load_reader()
        if not reader:
            return {}
        return reader.get_stats_summary()

    async def _run_audit_subprocess(
        self,
        rotate_models: bool = False,
        fast: bool = False,
        max_files: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Run `dockdesk audit` asynchronously and return execution metadata."""
        cmd = [
            sys.executable,
            "-m",
            "dockdesk",
            "audit",
            "--workspace",
            self.workspace,
        ]
        if rotate_models:
            cmd.append("--rotate-models")
        if fast:
            cmd.append("--fast")
        if max_files is not None and max_files > 0:
            cmd.extend(["--max-files", str(max_files)])

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.workspace,
        )
        out_b, err_b = await proc.communicate()
        return {
            "returncode": proc.returncode,
            "stdout": (out_b or b"").decode("utf-8", errors="ignore"),
            "stderr": (err_b or b"").decode("utf-8", errors="ignore"),
            "command": " ".join(cmd),
        }

    def run(self) -> None:
        """Start Discord bot event loop with slash commands."""
        try:
            import discord
            from discord import app_commands
            from discord.ext import commands
        except Exception as e:
            raise RuntimeError(
                "discord.py is required for bot mode. Install with 'pip install discord.py'."
            ) from e

        intents = discord.Intents.default()
        intents.guilds = True

        bot = commands.Bot(command_prefix="!", intents=intents)
        service = self

        group = app_commands.Group(name="dockdesk", description="DockDesk audit and reporting commands")

        @group.command(name="ping", description="Check if DockDesk bot is alive")
        async def ping(interaction: discord.Interaction):
            await interaction.response.send_message(
                f"DockDesk bot online for `{os.path.basename(service.workspace)}`.",
                ephemeral=True,
            )

        @group.command(name="status", description="Show latest DockDesk audit summary")
        async def status(interaction: discord.Interaction):
            latest = service._latest_run_summary()
            if not latest:
                await interaction.response.send_message(
                    "No audit history found. Run an audit first.",
                    ephemeral=True,
                )
                return

            risk = latest.get("risk_distribution", {})
            embed = discord.Embed(
                title="DockDesk Latest Run",
                description=f"Workspace: `{service.workspace}`",
                color=0x5865F2,
            )
            embed.add_field(
                name="Summary",
                value=(
                    f"Files: {latest.get('files_audited', 0)}\n"
                    f"Pass: {latest.get('pass_count', 0)}\n"
                    f"Fail: {latest.get('fail_count', 0)}"
                ),
                inline=True,
            )
            embed.add_field(
                name="Risk",
                value=(
                    f"HIGH: {risk.get('HIGH', 0)}\n"
                    f"MEDIUM: {risk.get('MEDIUM', 0)}\n"
                    f"LOW: {risk.get('LOW', 0)}"
                ),
                inline=True,
            )
            embed.add_field(
                name="Model",
                value=f"`{latest.get('model', 'unknown')}`",
                inline=False,
            )
            ts = str(latest.get("timestamp", ""))
            if ts:
                embed.set_footer(text=f"Run at {ts}")
            await interaction.response.send_message(embed=embed)

        @group.command(name="recent", description="Show recent DockDesk runs")
        async def recent(interaction: discord.Interaction):
            reader = service._load_reader()
            if not reader:
                await interaction.response.send_message(
                    "No audit history found.", ephemeral=True
                )
                return
            runs = reader.get_runs(limit=5)
            if not runs:
                await interaction.response.send_message("No runs available.", ephemeral=True)
                return

            lines = []
            for r in runs:
                ts = str(r.get("timestamp", ""))[:16].replace("T", " ")
                lines.append(
                    f"`{ts}` files={r.get('files_audited', 0)} pass={r.get('pass_count', 0)} fail={r.get('fail_count', 0)}"
                )
            await interaction.response.send_message("\n".join(lines))

        @group.command(name="audit", description="Trigger an audit run from Discord")
        @app_commands.describe(
            rotate_models="Enable round-robin code-model rotation",
            fast="Enable fast mode",
            max_files="Limit files audited (0 = all)",
        )
        async def audit(
            interaction: discord.Interaction,
            rotate_models: bool = False,
            fast: bool = False,
            max_files: int = 0,
        ):
            await interaction.response.defer(thinking=True)
            before = service._latest_run_summary().get("run_id")
            result = await service._run_audit_subprocess(
                rotate_models=rotate_models,
                fast=fast,
                max_files=max_files if max_files > 0 else None,
            )
            after = service._latest_run_summary()
            after_id = after.get("run_id")

            code = result.get("returncode", 1)
            if code == 0:
                risk = after.get("risk_distribution", {}) if after else {}
                msg = (
                    "Audit complete.\n"
                    f"Run: `{after_id}`\n"
                    f"Files: {after.get('files_audited', 0) if after else 0}\n"
                    f"Pass/Fail: {after.get('pass_count', 0) if after else 0}/{after.get('fail_count', 0) if after else 0}\n"
                    f"Risk H/M/L: {risk.get('HIGH', 0)}/{risk.get('MEDIUM', 0)}/{risk.get('LOW', 0)}"
                )
                if before == after_id:
                    msg += "\nNote: run metadata did not change; check local logs."
                await interaction.followup.send(msg)
            else:
                stderr = (result.get("stderr") or "").strip()
                if len(stderr) > 1200:
                    stderr = stderr[:1200] + "\n... (truncated)"
                await interaction.followup.send(
                    "Audit failed.\n"
                    f"Command: `{result.get('command', '')}`\n"
                    f"Exit code: {code}\n"
                    f"```\n{stderr or 'No stderr output'}\n```"
                )

        @bot.event
        async def on_ready():
            if self.guild_id:
                guild = discord.Object(id=self.guild_id)
                bot.tree.add_command(group, guild=guild)
                await bot.tree.sync(guild=guild)
                console.print(f"[green]Discord bot ready (guild-scoped sync: {self.guild_id}).[/green]")
            else:
                bot.tree.add_command(group)
                await bot.tree.sync()
                console.print("[green]Discord bot ready (global slash-command sync).[/green]")

        bot.run(self.token)


def run_discord_bot(workspace: str, token: str, guild_id: Optional[int] = None) -> None:
    """Convenience entrypoint for CLI integration."""
    svc = DiscordBotService(workspace=workspace, token=token, guild_id=guild_id)
    svc.run()
