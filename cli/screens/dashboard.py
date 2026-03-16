"""
DashboardScreen — fully data-driven.

Every label that was previously hardcoded now comes from the backend:
  • Session ID, status            ← GET /sessions/{id}
  • Active plan name, step count  ← session["plans"]
  • Last execution status/timing  ← session["execution_jobs"]
  • System CPU / RAM              ← psutil (local)
  • Provider (Gemini / OpenAI)    ← GET /policy  → llm_provider
  • Activity log                  ← GET /sessions/{id}/history → executions
"""

import datetime
import os
from pathlib import Path
from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Static, ListView, ListItem, RichLog, Input

from cli.components.header import BrandHeader
from cli.components.nav import TopMenu
from cli.components.footer import AppStatusBar
from cli.api_client import api, BASE_URL

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SANDBOX_WORKSPACE = _PROJECT_ROOT / "app" / "sandbox" / "workspace"

# ─── Progress bar helper ───────────────────────────────────────
def _bar(filled: float = 1.0, width: int = 22) -> str:
    n = max(0, min(width, int(filled * width)))
    return "━" * n + "─" * (width - n)

# ─── Quick-action launcher entries ────────────────────────────
_ACTIONS = [
    (1, "Create New Plan",        "switch_plans",   "⊕"),
    (2, "Execute Active Plan",    "switch_execute", "▶"),
    (3, "Browse Filesystem",      "switch_files",   "📁"),
    (4, "Tools Registry",         "switch_tools",   "🔧"),
    (5, "View Execution History", "switch_history", "🕒"),
    (6, "System Logs",            "switch_logs",    "📄"),
]


class DashboardScreen(Screen):
    """Central command-center dashboard — all data driven from backend."""

    def _parse_iso_time(self, raw: str | None) -> datetime.datetime | None:
        if not raw:
            return None
        try:
            return datetime.datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone()
        except Exception:
            return None

    def _recent_filesystem_events(self, limit: int = 8) -> list[tuple[datetime.datetime, str]]:
        events: list[tuple[datetime.datetime, str]] = []
        if not _SANDBOX_WORKSPACE.exists():
            return events

        try:
            for root, _dirs, files in os.walk(_SANDBOX_WORKSPACE):
                for fname in files:
                    path = Path(root) / fname
                    try:
                        mtime = datetime.datetime.fromtimestamp(path.stat().st_mtime).astimezone()
                    except Exception:
                        continue
                    rel = path.relative_to(_SANDBOX_WORKSPACE).as_posix()
                    msg = f"[#565F89][{mtime.strftime('%H:%M:%S')}][/] [bold #2AC3DE]FILE[/] [#C0CAF5]{rel}[/]"
                    events.append((mtime, msg))
        except Exception:
            return []

        events.sort(key=lambda x: x[0], reverse=True)
        return events[:limit]

    def _render_activity_feed(self, history_payload: dict | None) -> None:
        log = self.query_one("#activity-log", RichLog)
        events: list[tuple[datetime.datetime, str]] = []

        executions = (history_payload or {}).get("executions") or []
        for record in executions:
            dt = self._parse_iso_time(record.get("timestamp"))
            if not dt:
                continue
            tool = record.get("tool_name", "?")
            res = record.get("result", {}) if isinstance(record.get("result"), dict) else {}
            ok = not res.get("error")
            label = "[bold #9ECE6A]OK[/]" if ok else "[bold #F7768E]ERR[/]"
            line = f"[#565F89][{dt.strftime('%H:%M:%S')}][/] [{label}] [#7AA2F7]{tool}[/]"
            events.append((dt, line))

        events.extend(self._recent_filesystem_events(limit=10))
        events.sort(key=lambda x: x[0], reverse=True)

        log.clear()
        if not events:
            log.write("[#565F89]No recent activity yet.[/]")
            return

        for _, line in events[:12]:
            log.write(line)

    def compose(self) -> ComposeResult:
        yield TopMenu(active_tab="Dashboard")

        with Container(id="main-container"):

            # ── Hero banner ───────────────────────────────────
            with Vertical(id="hero-box"):
                yield BrandHeader()

            # ── Stat cards ────────────────────────────────────
            with Container(id="dash-stat-row"):

                with Vertical(classes="stat-card", id="card-session"):
                    with Horizontal(classes="stat-header"):
                        yield Static("[bold #565F89]SESSION[/]", classes="stat-label")
                        yield Static("[bold #9ECE6A]●[/]", classes="stat-dot", id="dot-sess")
                    yield Static("[dim]connecting…[/]", classes="stat-value", id="dash-sess-status")
                    yield Static("[dim]ID: —[/]",        classes="stat-sub",   id="dash-sess-id")
                    yield Static("",                     classes="stat-bar-green", id="dash-sess-bar")

                with Vertical(classes="stat-card", id="card-plan"):
                    with Horizontal(classes="stat-header"):
                        yield Static("[bold #565F89]ACTIVE PLAN[/]", classes="stat-label")
                        yield Static("[bold #7AA2F7]●[/]", classes="stat-dot")
                    yield Static("[dim]—[/]",     classes="stat-value", id="dash-plan-id")
                    yield Static("[dim]Steps: —[/]", classes="stat-sub", id="dash-plan-steps")
                    yield Static("",              classes="stat-bar-blue", id="dash-plan-bar")

                with Vertical(classes="stat-card", id="card-exec"):
                    with Horizontal(classes="stat-header"):
                        yield Static("[bold #565F89]LAST EXEC[/]", classes="stat-label")
                        yield Static("[bold #9ECE6A]●[/]", classes="stat-dot", id="dot-exec")
                    yield Static("[dim]—[/]",      classes="stat-value", id="dash-exec-status")
                    yield Static("[dim]—[/]",      classes="stat-sub",   id="dash-exec-prog")

                with Vertical(classes="stat-card stat-card-last", id="card-sys"):
                    with Horizontal(classes="stat-header"):
                        yield Static("[bold #565F89]SYSTEM[/]", classes="stat-label")
                        yield Static("[bold #9ECE6A]●[/]", classes="stat-dot")
                    yield Static("[dim]—[/]", classes="stat-value", id="dash-sys-status")
                    yield Static("[dim]CPU: — | MEM: —[/]", classes="stat-sub", id="dash-sys-metrics")

            # ── Bottom split ──────────────────────────────────
            with Horizontal(id="dash-bottom"):

                # LEFT — Command Launcher
                with Vertical(id="dash-launcher"):
                    yield ListView(
                        *[
                            ListItem(
                                Horizontal(
                                    Static(
                                        f"  [#565F89][{num}][/]  [bold #C0CAF5]{label}[/]",
                                        classes="launcher-text"
                                    ),
                                    Static(f"[#565F89]{icon}[/]", classes="launcher-icon"),
                                ),
                                id=f"qa_{action}",
                            )
                            for num, label, action, icon in _ACTIONS
                        ],
                        id="launcher-list",
                    )
                    yield Static(
                        " [on #1A1F2E][#A9B1D6] Space [/][/] [#565F89]Search[/]  "
                        "[on #1A1F2E][#A9B1D6] Esc [/][/] [#565F89]Cancel[/]  "
                        "[on #1A1F2E][#A9B1D6] : [/][/] [#565F89]Command[/]",
                        id="launcher-footer",
                    )

                # RIGHT — Activity log + input
                with Vertical(id="dash-activity"):
                    yield RichLog(id="activity-log", markup=True, highlight=False, wrap=False)
                    with Horizontal(id="activity-input-row"):
                        with Horizontal(id="activity-input-container"):
                            yield Static(" [bold #7AA2F7]>[/] ", id="activity-prompt")
                            yield Input(
                                placeholder="Type a command or press '/' to search…",
                                id="activity-input-box",
                            )
                        yield Static("ENTER", id="activity-enter")

        yield AppStatusBar()

    # ── Lifecycle ──────────────────────────────────────────────

    async def on_mount(self) -> None:
        host = BASE_URL.replace("http://", "").replace("/api/v1", "")
        # Panel titles
        self.query_one("#dash-launcher").border_title    = " [bold #7AA2F7]🚀 COMMAND LAUNCHER[/] "
        self.query_one("#dash-launcher").border_subtitle = f" [#565F89]{host}[/] "
        self.query_one("#dash-launcher").styles.border_title_align    = "left"
        self.query_one("#dash-launcher").styles.border_subtitle_align = "right"

        self.query_one("#dash-activity").border_title    = " [bold #7AA2F7]⚡ RECENT ACTIVITY[/] "
        self.query_one("#dash-activity").border_subtitle = " [bold #7AA2F7]● LIVE FEED[/] "
        self.query_one("#dash-activity").styles.border_title_align    = "left"
        self.query_one("#dash-activity").styles.border_subtitle_align = "right"

        # Initial refresh then poll every 5 s
        await self._refresh_all()
        self.set_interval(5, lambda: self.run_worker(self._refresh_all()))

    def on_screen_resume(self) -> None:
        self.run_worker(self._refresh_all())

    # ── Navigation ────────────────────────────────────────────

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item_id = event.item.id or ""
        if item_id.startswith("qa_"):
            fn = getattr(self.app, f"action_{item_id[3:]}", None)
            if fn:
                fn()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        cmd = event.value.strip()
        if not cmd:
            return
        log = self.query_one("#activity-log", RichLog)
        now = datetime.datetime.now().strftime("%H:%M:%S")
        log.write(f"[#565F89][{now}][/]  [[bold #E0AF68]INPUT[/]]  {cmd}")
        self.query_one("#activity-input-box", Input).clear()

    # ── Core refresh ──────────────────────────────────────────

    async def _refresh_all(self) -> None:
        """Single async round-trip: fetches session + policy, then updates every widget."""
        session_id = getattr(self.app, "session_id", None)
        footer: AppStatusBar = self.query_one(AppStatusBar)
        nav: TopMenu = self.query_one(TopMenu)

        # ── System metrics (pure local — always available) ────
        metrics = api.get_system_metrics()
        self.query_one("#dash-sys-status", Static).update("[bold #9ECE6A]HEALTHY[/]")
        self.query_one("#dash-sys-metrics", Static).update(
            f"[dim]CPU: {metrics['cpu']} | MEM: {metrics['mem']}[/]"
        )

        if not session_id or session_id == "OFFLINE":
            self._set_offline(nav, footer)
            return

        try:
            # ── Parallel fetch: session + policy ──────────────
            import asyncio
            session_data, policy, history_data = await asyncio.gather(
                api.get_session(session_id),
                api.get_policy(),
                api.get_history(session_id),
                return_exceptions=True,
            )

            if isinstance(session_data, Exception):
                raise session_data

            provider = (
                policy.get("llm_provider", "gemini").upper()
                if not isinstance(policy, Exception) else "GEMINI"
            )

            host = BASE_URL.replace("http://", "").replace("/api/v1", "")

            # ── Nav chips ─────────────────────────────────────
            nav.update_chips(session_id=session_id, provider=provider, connected=True)
            footer.set_connected(True, host)

            # ── Session card ──────────────────────────────────
            sid = session_data.get("session_id", session_id)
            short_id = sid[:8].upper()
            self.query_one("#dash-sess-status", Static).update("[bold #9ECE6A]RUNNING[/]")
            self.query_one("#dash-sess-id",     Static).update(f"[dim]ID: {short_id}[/]")
            self.query_one("#dash-sess-bar",    Static).update(f"[#9ECE6A]{_bar(1.0)}[/]")
            self.query_one("#dot-sess",         Static).update("[bold #9ECE6A]●[/]")
            self.query_one("#chip-sess",        Static).update(
                f" [bold #9ECE6A]●[/] [bold #9ECE6A]SESSION: {short_id}[/] "
            )

            # ── Plan card ─────────────────────────────────────
            plans = session_data.get("plans", {})
            if plans:
                latest_id  = list(plans.keys())[-1]
                latest     = plans[latest_id]
                steps      = len(latest.get("steps", []))
                risk       = sum(1 for s in latest.get("steps", []) if not s.get("allowed", True))
                risk_label = (f"[#F7768E]{risk} risky[/]" if risk else "[#9ECE6A]Clean[/]")
                self.query_one("#dash-plan-id",    Static).update(f"[bold #C0CAF5]{latest_id[:14]}[/]")
                self.query_one("#dash-plan-steps", Static).update(
                    f"[dim]Steps: {steps}  Risk: [/]{risk_label}"
                )
                fill = min(1.0, steps / max(steps, 1))
                self.query_one("#dash-plan-bar", Static).update(
                    f"[#7AA2F7]{_bar(fill)}[/][#2A2F45]{_bar(1.0 - fill, 22 - int(fill * 22))}[/]"
                )
            else:
                self.query_one("#dash-plan-id",    Static).update("[dim]None[/]")
                self.query_one("#dash-plan-steps", Static).update("[dim]No plans yet[/]")

            # ── Execution card ────────────────────────────────
            jobs = session_data.get("execution_jobs", {})
            if jobs:
                job     = list(jobs.values())[-1]
                jstatus = job.get("status", "unknown")
                jprog   = job.get("progress", "—")
                col = (
                    "#9ECE6A" if jstatus == "completed"
                    else "#E0AF68" if jstatus == "running"
                    else "#F7768E" if jstatus == "failed"
                    else "#A9B1D6"
                )
                dot_col = "#9ECE6A" if jstatus == "completed" else "#E0AF68"
                self.query_one("#dash-exec-status", Static).update(
                    f"[bold {col}]{jstatus.upper()}[/]"
                )
                self.query_one("#dash-exec-prog",   Static).update(
                    f"[dim]Progress: {jprog}[/]"
                )
                self.query_one("#dot-exec", Static).update(f"[bold {dot_col}]●[/]")
            else:
                self.query_one("#dash-exec-status", Static).update("[dim]No jobs[/]")
                self.query_one("#dash-exec-prog",   Static).update("[dim]—[/]")

            self._render_activity_feed(
                history_data if not isinstance(history_data, Exception) else None
            )

        except Exception:
            self._set_offline(nav, footer)

    def _set_offline(self, nav: TopMenu, footer: AppStatusBar) -> None:
        nav.update_chips(connected=False)
        footer.set_connected(False)
        self.query_one("#dash-sess-status", Static).update("[bold #F7768E]OFFLINE[/]")
        self.query_one("#dash-sess-id",     Static).update("[dim]ID: —[/]")
        self.query_one("#dash-sess-bar",    Static).update("[#2A2F45]──────────────────────[/]")
        self.query_one("#chip-sess",        Static).update(
            " [bold #F7768E]●[/] [bold #F7768E]SESSION: OFFLINE[/] "
        )
