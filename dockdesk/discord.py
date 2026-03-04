"""
DockDesk Discord Webhook Integration

Posts audit summaries, push-guard notifications, and reasoning verdicts
to a Discord channel via webhook. Zero-infrastructure — just an HTTP POST.

All methods are no-ops when no webhook URL is configured.
Failures log warnings but never crash the pipeline.
"""

import os
import json
import time
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
            title = "\U0001f6a8 DockDesk Audit — HIGH Risk Detected"
        elif medium > 0:
            colour = 0xFEE75C   # yellow
            title = "\u26a0\ufe0f DockDesk Audit — Medium Risk"
        else:
            colour = 0x57F287   # green
            title = "\u2705 DockDesk Audit — All Clear"

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
            "description": summary or "Audit passed — no HIGH risk findings.",
            "footer": {"text": "DockDesk Pre-Push Guard"},
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        return self._send({"embeds": [embed]})

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
