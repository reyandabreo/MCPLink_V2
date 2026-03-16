import os
from datetime import datetime, timezone
from pathlib import Path
from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Container, Vertical, VerticalScroll, Horizontal
from textual.widgets import Static, DataTable, RichLog, Input
from textual import work

from cli.components.nav import TopMenu, get_shortcut_str
from cli.api_client import api

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_LOG_DIR = _PROJECT_ROOT / "app" / "logs"


def _fmt_ts(iso: str) -> str:
    """Format an ISO timestamp to a short readable string."""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%m/%d  %H:%M")
    except Exception:
        return iso[:16] if iso else "--"


class HistoryScreen(Screen):
    """View session history — prompts and execution records."""

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("r", "action_refresh_history", "Refresh"),
        ("/", "focus_history_search", "Search"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.raw_history: list[dict] = []
        self.filtered_history: list[dict] = []

    def compose(self) -> ComposeResult:
        yield TopMenu(active_tab="History")

        with Container(id="hist-main-container"):
            with Horizontal(id="hist-top-row"):
                yield Static("[bold #7aa2f7]HISTORY[/] [#565f89]EXPLORER[/]", id="hist-title")
                yield Input(placeholder="Search history... [/]", id="hist-search")

            with Horizontal(id="hist-body"):
                with Vertical(id="hist-timeline-panel"):
                    with Horizontal(id="hist-timeline-head"):
                        yield Static("[bold #565f89]ACTIVITY TIMELINE[/]", id="hist-timeline-title")
                        yield Static("⟲", id="hist-timeline-icon")
                    with VerticalScroll(id="hist-timeline-scroll"):
                        yield Vertical(id="hist-timeline-list")
                    yield Static("[dim]End of Session[/]", id="hist-timeline-foot")

                with Vertical(id="hist-explorer-panel"):
                    with Horizontal(id="hist-explorer-head"):
                        yield Static("[bold #565f89]HISTORY EXPLORER[/]", id="hist-explorer-title")
                        yield Static("[#f7768e]●[/] [#e0af68]●[/] [#9ece6a]●[/]", id="hist-explorer-lights")
                    yield DataTable(id="history-table", cursor_type="row", zebra_stripes=False)
                    yield Static("", id="hist-table-foot")

                with Vertical(id="hist-inspector-panel"):
                    with Horizontal(id="hist-inspector-head"):
                        yield Static("[bold #565f89]INSPECTOR PANEL[/]", id="hist-inspector-title")
                        yield Static("●", id="hist-inspector-icon")

                    with VerticalScroll(id="hist-inspector-scroll"):
                        yield Static("[bold #7aa2f7]SUMMARY[/]", id="hist-summary-label")
                        yield Static("[dim]Select a history row to inspect details.[/dim]", id="hist-summary-box")

                        with Horizontal(id="hist-tabs-row"):
                            yield Static("[bold #7aa2f7]LOGS[/]", classes="hist-tab hist-tab-active")
                            yield Static("[dim]STEPS[/]", classes="hist-tab")
                            yield Static("[dim]TOOLS[/]", classes="hist-tab")

                        yield Static("[dim]No details loaded.[/dim]", id="hist-detail")
                        yield Static("[bold #7aa2f7]RESOURCES USED[/]", id="hist-resources-title")
                        yield Static("[dim]No resources detected.[/dim]", id="hist-resources")

                    yield Static("[dim]Meta Data Loaded[/]", id="hist-inspector-foot")

            yield Static(
                "[dim]↑↓[/] Navigate   [dim]Enter[/] Inspect   [dim]/[/] Search   "
                "[dim]R[/] Refresh   [dim]Esc[/] Back",
                id="hist-bottom-help",
            )

    async def on_mount(self) -> None:
        table = self.query_one("#history-table", DataTable)
        table.add_column("ID",       width=6,  key="id")
        table.add_column("Type",     width=13, key="type")
        table.add_column("Status",   width=11, key="status")
        table.add_column("Duration", width=10, key="duration")
        table.add_column("When",     width=10, key="when")
        table.add_column("Summary",            key="summary")

        session_id = getattr(self.app, "session_id", None)
        sess_info = self.query_one("#chip-sess", Static)
        if session_id and session_id != "OFFLINE":
            sess_info.update(f" [bold #9ECE6A]●[/] [#9ECE6A]SESSION:[/] [bold #C0CAF5]{session_id[:8]}[/] ")
        else:
            sess_info.update(" [bold #F7768E]●[/] [#F7768E]SESSION:[/] [bold #F7768E]OFFLINE[/] ")

        self.query_one("#hist-main-container").border_subtitle = get_shortcut_str()

        self.fetch_history()

    def update_status(self) -> None:
        pass

    @work(exclusive=True)
    async def fetch_history(self) -> None:
        session_id = getattr(self.app, "session_id", None)
        if not session_id or session_id == "OFFLINE":
            self.query_one("#hist-detail", Static).update(
                "[#d29922]⚠  No backend session — history unavailable offline.[/]"
            )
            return
        try:
            session = await api.get_session(session_id)
        except Exception as e:
            self.query_one("#hist-detail", Static).update(
                f"[#f85149]✖  Failed to load history: {e}[/]"
            )
            return

        plans       = session.get("plans", {})          # plan_id → plan dict
        jobs        = session.get("execution_jobs", {})  # job_id  → job dict

        # Build unified timeline from plans and execution jobs.
        self.raw_history = []
        for plan_id, plan in plans.items():
            self.raw_history.append({"type": "plan", "id": plan_id, "data": plan})
        for job_id, job in jobs.items():
            self.raw_history.append({"type": "exec", "id": job_id,  "data": job})

        # Newest first for timeline and explorer.
        self.raw_history.reverse()

        if not self.raw_history:
            self.query_one("#hist-detail", Static).update(
                "[#7d8590]No history yet for this session.\n\n"
                "Create a plan in the Plans section to get started.[/]"
            )
            self.query_one("#hist-summary-box", Static).update("[dim]No records available.[/dim]")
            self.query_one("#hist-table-foot", Static).update("[dim]TOTAL RECORDS: 0  |  FILTER: NONE[/]")
            self._render_timeline()
            return
        self._apply_filter_and_render()

    @staticmethod
    def _status_style(status: str) -> str:
        stat = (status or "").lower()
        if stat in {"completed", "success", "done"}:
            return "[#9ece6a]●[/] [bold #9ece6a]Success[/]"
        if stat in {"created", "queued", "running", "pending"}:
            return "[#e0af68]●[/] [bold #e0af68]Created[/]"
        if stat in {"failed", "error"}:
            return "[#f7768e]●[/] [bold #f7768e]Failed[/]"
        return f"[#565f89]●[/] [bold #565f89]{status or 'Unknown'}[/]"

    @staticmethod
    def _relative_time(iso: str | None) -> str:
        if not iso:
            return "--"
        try:
            dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            delta = max(0, int((now - dt).total_seconds()))
            if delta < 60:
                return f"{delta}s ago"
            if delta < 3600:
                return f"{delta // 60}m ago"
            return f"{delta // 3600}h ago"
        except Exception:
            return "--"

    @staticmethod
    def _duration_label(rtype: str, data: dict) -> str:
        if "duration_seconds" in data:
            try:
                return f"{float(data['duration_seconds']):.1f}s"
            except Exception:
                pass
        if rtype == "exec":
            results = data.get("results", [])
            if isinstance(results, list) and results:
                return f"{len(results) * 2}s"
            if data.get("status") == "running":
                return "..."
            return "-"
        steps = data.get("steps", [])
        if isinstance(steps, list) and steps:
            return f"{len(steps)} st"
        return "-"

    def _record_model(self, record: dict) -> dict:
        rtype = record["type"]
        data = record["data"]
        rid = record["id"]
        created_iso = data.get("created_at")
        status = data.get("status", "unknown")

        if rtype == "plan":
            tool_type = "repo-analysis"
            prompt = data.get("prompt", data.get("goal", "—"))
            summary = prompt[:52] + ("..." if len(prompt) > 52 else "")
        else:
            tool_type = (data.get("mode") or "code-audit").replace("_", "-")
            summary = f"plan:{str(data.get('plan_id', '—'))[:8]} {data.get('progress', '')}".strip()

        return {
            "id": rid,
            "type": rtype,
            "tool_type": tool_type,
            "status": status,
            "duration": self._duration_label(rtype, data),
            "when": self._relative_time(created_iso),
            "summary": summary,
            "created": _fmt_ts(created_iso or ""),
            "data": data,
        }

    def _render_table(self) -> None:
        from rich.text import Text

        table = self.query_one("#history-table", DataTable)
        table.clear()

        for idx, rec in enumerate(self.filtered_history):
            rid = f"#{rec['id'][:4]}"
            if rec["type"] == "plan":
                type_chip = Text(rec["tool_type"], style="bold #7aa2f7")
            else:
                type_chip = Text(rec["tool_type"], style="bold #2ac3de")
            table.add_row(
                Text(rid, style="bold #7aa2f7"),
                type_chip,
                Text.from_markup(self._status_style(rec["status"])),
                Text(rec["duration"], style="#565f89"),
                Text(rec["when"], style="#565f89"),
                Text(rec["summary"], style="#c0caf5"),
                key=str(idx),
            )

    def _render_timeline(self) -> None:
        timeline = self.query_one("#hist-timeline-list", Vertical)
        for child in list(timeline.children):
            child.remove()

        if not self.filtered_history:
            timeline.mount(Static("[dim]No timeline events.[/dim]", classes="hist-timeline-empty"))
            return

        for rec in self.filtered_history[:25]:
            stat = (rec["status"] or "").lower()
            if stat in {"completed", "success", "done"}:
                color = "#9ece6a"
                title = "Execution Completed" if rec["type"] == "exec" else "Plan Completed"
            elif stat in {"failed", "error"}:
                color = "#f7768e"
                title = "Execution Failed" if rec["type"] == "exec" else "Plan Failed"
            elif rec["type"] == "plan":
                color = "#2ac3de"
                title = "Plan Created"
            else:
                color = "#e0af68"
                title = "Execution Created"

            timeline.mount(
                Static(
                    f"[{color}]●[/] [bold {color}]{title}[/]\n[dim]{rec['created']}[/]",
                    classes="hist-timeline-item",
                )
            )

    def _render_footer(self, filter_text: str) -> None:
        total = len(self.raw_history)
        filtered = len(self.filtered_history)
        if filter_text:
            text = f"[dim]TOTAL RECORDS: {total}  |  VISIBLE: {filtered}  |  FILTER: {filter_text}[/]"
        else:
            text = f"[dim]TOTAL RECORDS: {total}  |  PAGE 1  |  FILTER: NONE[/]"
        self.query_one("#hist-table-foot", Static).update(text)

    def _update_inspector(self, rec: dict | None) -> None:
        if not rec:
            self.query_one("#hist-summary-box", Static).update("[dim]Select a history row to inspect details.[/dim]")
            self.query_one("#hist-detail", Static).update("[dim]No details loaded.[/dim]")
            self.query_one("#hist-resources", Static).update("[dim]No resources detected.[/dim]")
            return

        rid = rec["id"]
        status = rec["status"]
        self.query_one("#hist-summary-box", Static).update(
            "\n".join([
                f"[#565f89]Execution ID:[/] [bold #7aa2f7]{rid[:24]}[/]",
                f"[#565f89]Duration:[/] [bold #2ac3de]{rec['duration']}[/]",
                f"[#565f89]Status:[/] {self._status_style(status)}",
            ])
        )

        data = rec["data"]
        if rec["type"] == "plan":
            steps = data.get("steps", []) if isinstance(data.get("steps", []), list) else []
            logs = [
                f"[dim][{i+1:02d}][/dim] [#7aa2f7]PLAN[/] {s.get('tool_name', '?')}"
                for i, s in enumerate(steps[:12])
            ]
            detail = "\n".join(logs) if logs else "[dim]No plan step logs available.[/dim]"
            resource_names = sorted({s.get("tool_name", "?") for s in steps if s.get("tool_name")})
        else:
            results = data.get("results", []) if isinstance(data.get("results", []), list) else []
            logs = []
            for i, r in enumerate(results[-12:]):
                ok = r.get("status") == "success"
                tag = "[#9ece6a][OK][/]" if ok else "[#f7768e][FAIL][/]"
                logs.append(f"[dim][{i+1:02d}][/dim] {tag} [#c0caf5]{r.get('tool_name', '?')}[/]")
            detail = "\n".join(logs) if logs else "[dim]No execution logs available.[/dim]"
            resource_names = sorted({r.get("tool_name", "?") for r in results if r.get("tool_name")})

        self.query_one("#hist-detail", Static).update(detail)
        if resource_names:
            chips = "  ".join(f"[#2ac3de][{name}][/ ]".replace("[/ ]", "[/]") for name in resource_names[:10])
            self.query_one("#hist-resources", Static).update(chips)
        else:
            self.query_one("#hist-resources", Static).update("[dim]No resources detected.[/dim]")

    def _apply_filter_and_render(self) -> None:
        filter_text = self.query_one("#hist-search", Input).value.strip().lower()

        if not filter_text:
            self.filtered_history = [self._record_model(r) for r in self.raw_history]
        else:
            filtered: list[dict] = []
            for r in self.raw_history:
                model = self._record_model(r)
                hay = " ".join([
                    model["id"],
                    model["tool_type"],
                    model["status"],
                    model["summary"],
                ]).lower()
                if filter_text in hay:
                    filtered.append(model)
            self.filtered_history = filtered

        self._render_table()
        self._render_timeline()
        self._render_footer(filter_text)

        if self.filtered_history:
            self._update_inspector(self.filtered_history[0])
        else:
            self._update_inspector(None)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        try:
            idx = int(event.row_key.value)
            rec = self.filtered_history[idx]
            self._update_inspector(rec)
        except Exception:
            pass

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "hist-search":
            self._apply_filter_and_render()

    def action_focus_history_search(self) -> None:
        self.query_one("#hist-search", Input).focus()

    def action_refresh_history(self) -> None:
        self.query_one("#history-table", DataTable).clear()
        self.query_one("#hist-detail", Static).update("[dim]Refreshing...[/dim]")
        self.fetch_history()


class LogsScreen(Screen):
    """Live-tail execution logs from app/logs/execution.log."""

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("r", "action_refresh_logs", "Refresh"),
    ]

    def compose(self) -> ComposeResult:
        yield TopMenu(active_tab="Logs")

        with Container(id="main-container"):
            with Vertical(id="panel-logs"):
                yield Static("", id="log-file-label")
                yield RichLog(id="log-output", markup=True, highlight=False)

            yield Static(
                "\n[bold #58a6ff][R][/] Refresh  [bold #58a6ff][Esc][/] Back",
                classes="hotkey-menu",
            )

    async def on_mount(self) -> None:
        self.query_one("#main-container").border_subtitle = get_shortcut_str()
        self.query_one("#panel-logs").border_title = (
            " [bold #58a6ff]\u25cf LIVE[/]  execution.log  [#7d8590]last 50 lines[/] "
        )

        session_id = getattr(self.app, "session_id", None)
        sess_info = self.query_one("#chip-sess", Static)
        if session_id and session_id != "OFFLINE":
            sess_info.update(f" [bold #9ECE6A]●[/] [#9ECE6A]SESSION:[/] [bold #C0CAF5]{session_id[:8]}[/] ")
        else:
            sess_info.update(" [bold #F7768E]●[/] [#F7768E]SESSION:[/] [bold #F7768E]OFFLINE[/] ")

        self.action_refresh_logs()

    def update_status(self) -> None:
        pass

    def action_refresh_logs(self) -> None:
        log_path = _LOG_DIR / "execution.log"
        label = self.query_one("#log-file-label", Static)
        log_widget = self.query_one("#log-output", RichLog)
        log_widget.clear()

        _BADGES = {
            "ERROR":   "[bold white on #f85149] ERR  [/]",
            "WARNING": "[bold black on #d29922] WARN [/]",
            "WARN":    "[bold black on #d29922] WARN [/]",
            "INFO":    "[bold black on #58a6ff] INFO [/]",
            "DEBUG":   "[bold white on #484f58] DBG  [/]",
        }
        _COLORS = {
            "ERROR":   "#f85149",
            "WARNING": "#d29922",
            "WARN":    "#d29922",
            "INFO":    "#c0caf5",
            "DEBUG":   "#7d8590",
        }

        if not log_path.exists():
            label.update(
                f"[#d29922]\u26a0  Log not found:[/] [#7d8590]{log_path}[/]"
            )
            log_widget.write(
                "[bold black on #d29922] WARN [/] [#d29922]Start the backend to generate logs.[/]"
            )
            return

        label.update(f"[#7d8590]\u25b8 File:[/] [bold #58a6ff]{log_path}[/]")

        try:
            with open(log_path, "r", errors="replace") as fh:
                lines = fh.readlines()[-50:]

            for raw_line in lines:
                line = raw_line.rstrip()
                if not line:
                    continue
                level = "INFO"
                for kw in ("ERROR", "WARNING", "WARN", "DEBUG"):
                    if kw in line:
                        level = kw
                        break
                badge = _BADGES[level]
                color = _COLORS[level]
                log_widget.write(f"{badge} [{color}]{line}[/]")

        except Exception as e:
            log_widget.write(f"[bold white on #f85149] ERR  [/] [#f85149]Failed to read log: {e}[/]")

