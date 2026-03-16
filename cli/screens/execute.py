"""
ExecuteScreen — matches HTML reference design:
  Left  panel: Progress bar · Policy status · Tool queue
  Right top:   ACTION header · explanation · args JSON block
  Right mid:   CPU · Memory · Files Read · Writes · Network metrics
  Bottom:      Live execution log with typed badges
  Footer:      [E] Execute  [K] Skip  [R] Retry  [Esc] Abort
"""

import asyncio
import datetime
from pathlib import Path
from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Container, Vertical, Horizontal, VerticalScroll
from textual.widgets import Static, RichLog
from textual import work

from cli.components.nav import TopMenu
from cli.api_client import api

# ── colour aliases ─────────────────────────────────────────────
_BL  = "#7aa2f7"
_DIM = "#565f89"
_GR  = "#9ece6a"
_YL  = "#e0af68"
_RD  = "#f7768e"
_PU  = "#bb9af7"
_FG  = "#c0caf5"
_BG  = "#0f111a"
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_WORKSPACE_HINT = str(_PROJECT_ROOT / "app" / "sandbox" / "workspace")

# ── log badge helpers ──────────────────────────────────────────
_BADGES = {
    "OK":   f"[bold black on {_GR} ] OK  [/]",
    "INFO": f"[bold black on {_BL} ]INFO [/]",
    "RUN":  f"[bold black on {_PU} ] RUN [/]",
    "WARN": f"[bold black on {_YL} ]WARN [/]",
    "ERR":  f"[bold white  on {_RD} ] ERR [/]",
    "STEP": f"[bold black on {_PU} ]STEP [/]",
}
_LOG_COL = {
    "OK": _GR, "INFO": _FG, "RUN": _PU,
    "WARN": _YL, "ERR": _RD, "STEP": _PU,
}


def _progress_bar(filled: int, total: int = 20, *, filled_char="█", empty_char="░") -> str:
    n = max(0, min(total, filled))
    return (
        f"[bold {_BL}]{filled_char * n}[/]"
        f"[{_DIM}]{empty_char * (total - n)}[/]"
    )


def _fmt_args_json(args: dict) -> str:
    """Pretty-print arguments as coloured pseudo-JSON."""
    if not args:
        return f"[{_DIM}](no arguments)[/]"
    lines = [f"[{_FG}]{{[/]"]
    items = list(args.items())
    for i, (k, v) in enumerate(items):
        val = str(v)
        if len(val) > 60:
            val = val[:57] + "…"
        comma = "," if i < len(items) - 1 else ""
        if isinstance(v, bool):
            col = _YL
        elif isinstance(v, (int, float)):
            col = _YL
        elif isinstance(v, str):
            col = _GR
            val = f'"{val}"'
        else:
            col = _FG
        lines.append(
            f"  [{_PU}]\"{k}\"[/]: [{col}]{val}[/]{comma}"
        )
    lines.append(f"[{_FG}]}}[/]")
    return "\n".join(lines)


class ExecuteScreen(Screen):
    BINDINGS = [
        ("e",      "execute_step",    "Execute Step"),
        ("k",      "skip_step",       "Skip Step"),
        ("r",      "retry_step",      "Retry"),
        ("escape", "app.pop_screen",  "Abort Session"),
    ]

    def __init__(self, plan_id: str = None, mode: str = "full", **kwargs):
        super().__init__(**kwargs)
        self.plan_id       = plan_id
        self.mode          = mode
        self.job_id        = None
        self.execution_active = False
        self._total_steps  = 0
        self._current_idx  = 0
        self._steps: list  = []
        self._log_widget: RichLog | None = None

    # ── Layout ────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield TopMenu(active_tab="Execute")

        # ── Workspace hero banner ──────────────────────────────────────────
        with Horizontal(id="exec-workspace-hero"):
            yield Static(
                "  [bold #2ac3de]ACTIVE WORKSPACE[/]",
                id="exec-hero-label",
            )
            yield Static(
                f"  [bold #c0caf5]{_WORKSPACE_HINT}[/]",
                id="exec-hero-path",
            )

        with Container(id="main-container"):
            with Horizontal(id="exec-body"):

                # ── LEFT: progress + policy + tool queue ──────
                with VerticalScroll(id="exec-left-panel"):

                    # Progress
                    yield Static(f"[bold {_DIM}]PROGRESS[/]", classes="exec-section-label")
                    yield Static("Step —/—", id="exec-step-label", classes="exec-big-label")
                    with Horizontal(id="exec-bar-row"):
                        yield Static("", id="exec-bar",    classes="exec-bar-text")
                        yield Static("0%", id="exec-pct", classes="exec-pct-text")

                    # Policy status
                    yield Static(
                        f"[bold {_DIM}]POLICY STATUS[/]",
                        classes="exec-section-label", id="exec-policy-heading"
                    )
                    yield Static(
                        f"[bold {_GR}]✔ ALLOWED[/]",
                        id="exec-policy-badge", classes="exec-policy-box"
                    )

                    # Tool queue
                    yield Static(
                        f"[bold {_DIM}]TOOL QUEUE[/]",
                        classes="exec-section-label", id="exec-queue-heading"
                    )
                    with Vertical(id="exec-queue-list"):
                        yield Static(
                            f"[{_DIM}]Loading…[/]", id="exec-queue-items"
                        )

                # ── RIGHT: action + metrics + log ─────────────
                with VerticalScroll(id="exec-right-side"):

                    # Action detail panel
                    with Vertical(id="exec-action-panel"):

                        with Horizontal(id="exec-action-header"):
                            yield Static(
                                f"[bold {_BL}]ACTION:[/]  [{_BL}]—[/]",
                                id="exec-action-name",
                            )
                            yield Static(
                                f"[{_DIM}]PID: —[/]",
                                id="exec-pid-label",
                                classes="exec-pid",
                            )

                        yield Static(
                            f"[{_DIM}]Waiting for step…[/]",
                            id="exec-explanation",
                            classes="exec-explanation-text",
                        )

                        # Args JSON block
                        with Vertical(id="exec-args-box"):
                            yield Static(
                                f"[{_DIM}]ARGUMENTS (JSON)[/]",
                                id="exec-args-box-label"
                            )
                            yield Static("", id="exec-args-json", classes="exec-args-json")

                    # Metrics row
                    with Horizontal(id="exec-metrics-row"):
                        with Vertical(classes="exec-metric-cell"):
                            yield Static(f"[{_DIM}]CPU LOAD[/]",  classes="exec-metric-label")
                            yield Static("—",                      classes="exec-metric-value", id="met-cpu")
                            yield Static("",                       classes="exec-mini-bar",     id="met-cpu-bar")

                        yield Static(f"[{_DIM}]│[/]", classes="exec-metric-sep")

                        with Vertical(classes="exec-metric-cell"):
                            yield Static(f"[{_DIM}]MEMORY[/]",    classes="exec-metric-label")
                            yield Static("—",                      classes="exec-metric-value", id="met-mem")
                            yield Static("",                       classes="exec-mini-bar",     id="met-mem-bar")

                        yield Static(f"[{_DIM}]│[/]", classes="exec-metric-sep")

                        with Vertical(classes="exec-metric-cell"):
                            yield Static(f"[{_DIM}]FILES READ[/]", classes="exec-metric-label")
                            yield Static("—",                       classes="exec-metric-value", id="met-files")
                            yield Static(f"[{_DIM}]—[/]",          classes="exec-metric-sub",   id="met-files-sub")

                        yield Static(f"[{_DIM}]│[/]", classes="exec-metric-sep")

                        with Vertical(classes="exec-metric-cell"):
                            yield Static(f"[{_DIM}]WRITES[/]",    classes="exec-metric-label")
                            yield Static("—",                      classes="exec-metric-value", id="met-writes")
                            yield Static(f"[{_DIM}]—[/]",         classes="exec-metric-sub",   id="met-writes-sub")

                        yield Static(f"[{_DIM}]│[/]", classes="exec-metric-sep")

                        with Vertical(classes="exec-metric-cell"):
                            yield Static(f"[{_DIM}]NETWORK[/]",   classes="exec-metric-label")
                            yield Static("0.0B",                   classes="exec-metric-value exec-metric-yellow", id="met-net")
                            yield Static(f"[{_GR}]Offline Sandbox[/]", classes="exec-metric-sub", id="met-net-sub")

                    # Live log
                    with Vertical(id="exec-log-panel"):
                        with Horizontal(id="exec-log-header"):
                            yield Static(
                                f"[bold {_DIM}]EXECUTION LOGS[/]  [bold {_GR}]●[/]",
                                id="exec-log-title"
                            )
                        yield RichLog(
                            id="exec-log",
                            markup=True,
                            highlight=False,
                            wrap=False,
                        )

        # Footer — fixed 3-row bar inside main-container
            with Horizontal(id="exec-footer"):
                with Horizontal(id="exec-footer-left"):
                    yield Static(
                        f"[on #1a1f2e][bold {_BL}] E [/][/] [{_DIM}]EXECUTE[/]",
                        classes="exec-hotkey"
                    )
                    yield Static(
                        f"[on #1a1f2e][bold {_FG}] K [/][/] [{_DIM}]SKIP[/]",
                        classes="exec-hotkey"
                    )
                    yield Static(
                        f"[on #1a1f2e][bold {_FG}] R [/][/] [{_DIM}]RETRY[/]",
                        classes="exec-hotkey"
                    )
                yield Static(
                    f"[on #1a1f2e][bold {_RD}] Esc [/][/] [bold {_RD}]ABORT SESSION[/]",
                    id="exec-abort-btn",
                )

    # ── Mount ─────────────────────────────────────────────────

    async def on_mount(self) -> None:
        self._log_widget = self.query_one("#exec-log", RichLog)
        self.query_one("#exec-left-panel").border_title  = " [bold #7AA2F7]⚡ Execution[/] "
        self.query_one("#exec-action-panel").border_title = " [bold #7AA2F7]Action Details[/] "
        self.query_one("#exec-metrics-row").border_title  = " [bold #BB9AF7]Sandbox I/O[/] "
        self.query_one("#exec-log-panel").border_title    = " [bold #9ECE6A]● Live Log[/] "

        # Seed metrics from psutil
        self._update_metrics()

        session_id = getattr(self.app, "session_id", None)
        if session_id and session_id != "OFFLINE":
            self.query_one("#met-net-sub", Static).update(f"[{_GR}]Connected Session[/]")
        else:
            self.query_one("#met-net-sub", Static).update(f"[{_GR}]Offline Sandbox[/]")

        if session_id and session_id != "OFFLINE":
            if not self.plan_id:
                try:
                    sess = await api.get_session(session_id)
                    plans = sess.get("plans", {})
                    if plans:
                        self.plan_id = list(plans.keys())[-1]
                except Exception:
                    pass

            if self.plan_id:
                await self._load_plan()
                if self.mode == "full":
                    self._log("INFO", f"Starting execution for plan [{_BL}]{self.plan_id[:8]}[/]…")
                    self.start_full_execution()
                else:
                    self._show_current_step()
            else:
                self._log("WARN", "No active plan found.")
        else:
            self._log("WARN", "Session OFFLINE — cannot execute.")

        # Poll system metrics every 3 s
        self.set_interval(3, self._update_metrics)

    # ── Data loading ──────────────────────────────────────────

    async def _load_plan(self) -> None:
        session_id = getattr(self.app, "session_id", None)
        try:
            plan = await api.get_plan(session_id, self.plan_id)
            self._steps = plan.get("steps", [])
            self._total_steps = len(self._steps)
            self._build_queue()
        except Exception as e:
            self._log("ERR", f"Could not load plan: {e}")

    def _build_queue(self) -> None:
        """Render the tool queue list in the left panel."""
        lines = []
        for i, step in enumerate(self._steps):
            tool = step.get("tool_name", "?")
            if i < self._current_idx:
                lines.append(f"[{_DIM}]  ✓  {tool}[/]")          # done
            elif i == self._current_idx:
                lines.append(f"  [bold {_BL}]▶  {tool}[/]")       # active
            else:
                lines.append(f"[{_DIM}]  ○  {tool}[/]")           # pending
        self.query_one("#exec-queue-items", Static).update("\n".join(lines) or f"[{_DIM}](empty)[/]")

    # ── Metrics ───────────────────────────────────────────────

    def _update_metrics(self) -> None:
        m = api.get_system_metrics()
        cpu_str = m.get("cpu", "—")
        mem_str = m.get("mem", "—")
        # CPU bar fill
        try:
            cpu_pct = float(cpu_str.replace("%", "")) / 100
        except Exception:
            cpu_pct = 0.0
        try:
            mem_mb  = int(mem_str.replace("MB", ""))
            mem_pct = min(1.0, mem_mb / 4096)         # assume 4 GB max
        except Exception:
            mem_pct = 0.0

        filled_c = "━" * int(cpu_pct * 8)
        empty_c  = "─" * (8 - int(cpu_pct * 8))
        filled_m = "━" * int(mem_pct * 8)
        empty_m  = "─" * (8 - int(mem_pct * 8))

        try:
            self.query_one("#met-cpu",     Static).update(f"[bold {_PU}]{cpu_str}[/]")
            self.query_one("#met-cpu-bar", Static).update(f"[{_PU}]{filled_c}[/][{_DIM}]{empty_c}[/]")
            self.query_one("#met-mem",     Static).update(f"[bold {_PU}]{mem_str}[/]")
            self.query_one("#met-mem-bar", Static).update(f"[{_PU}]{filled_m}[/][{_DIM}]{empty_m}[/]")
        except Exception:
            pass

    # ── Step display ──────────────────────────────────────────

    def _show_current_step(self) -> None:
        steps = self._steps
        total = self._total_steps
        idx   = self._current_idx

        # Find first pending
        pending = next((i for i, s in enumerate(steps) if s.get("status") == "pending"), None)
        if pending is not None:
            idx = pending
            self._current_idx = idx

        if not steps:
            return

        if idx >= total:
            self._show_all_done()
            return

        step    = steps[idx]
        tool    = step.get("tool_name", "unknown")
        expl    = step.get("explanation", "")
        args    = step.get("arguments", {})
        allowed = step.get("allowed", True)

        # Progress
        pct  = int((idx / max(total, 1)) * 100)
        fill = round(idx / max(total, 1) * 10)
        bar  = _progress_bar(fill, 10)

        self.query_one("#exec-step-label", Static).update(
            f"[bold {_FG}]Step {idx+1}/{total}[/]"
        )
        self.query_one("#exec-bar", Static).update(bar)
        self.query_one("#exec-pct", Static).update(f"[bold {_BL}]{pct}%[/]")

        # Policy
        if allowed:
            badge_txt = f"[bold black on {_GR}]  ✔ ALLOWED  [/]"
        else:
            warn = step.get("warning", "Policy violation")[:40]
            badge_txt = f"[bold black on {_RD}]  ✖ RESTRICTED  [/]  [{_DIM}]{warn}[/]"
        self.query_one("#exec-policy-badge", Static).update(badge_txt)

        # Action detail
        run_id = f"{(self.job_id or self.plan_id or 'local')[:8]}-{idx + 1:02d}"
        thread_id = f"{(getattr(self.app, 'session_id', '00') or '00')[-2:]}"
        self.query_one("#exec-action-name", Static).update(
            f"[bold {_BL}]ACTION:[/]  [on {_BL}20%][{_BL}] {tool} [/]"
        )
        self.query_one("#exec-pid-label", Static).update(
            f"[{_DIM}]RUN: {run_id} | Thread: 0x{thread_id}[/]"
        )
        self.query_one("#exec-explanation", Static).update(f"[{_FG}]{expl}[/]")
        self.query_one("#exec-args-json",   Static).update(_fmt_args_json(args))

        # Files/writes counters
        files_done = sum(1 for s in steps[:idx] if "read" in s.get("tool_name",""))
        writes_done= sum(1 for s in steps[:idx] if "write" in s.get("tool_name",""))
        try:
            self.query_one("#met-files",      Static).update(f"[bold {_BL}]{files_done}[/]")
            self.query_one("#met-writes",     Static).update(f"[bold {_GR}]{writes_done}[/]")
        except Exception:
            pass

        # Rebuild queue
        self._build_queue()

    def _show_all_done(self) -> None:
        total = self._total_steps
        bar   = f"[bold {_GR}]{'█' * 10}[/]"
        self.query_one("#exec-step-label", Static).update(f"[bold {_GR}]✔ All {total} steps done[/]")
        self.query_one("#exec-bar",        Static).update(bar)
        self.query_one("#exec-pct",        Static).update(f"[bold {_GR}]100%[/]")
        self.query_one("#exec-policy-badge", Static).update(
            f"[bold black on {_GR}]  COMPLETED  [/]"
        )
        self.query_one("#exec-action-name",  Static).update(f"[bold {_GR}]✔ Execution Complete[/]")
        self.query_one("#exec-explanation",  Static).update("")
        self.query_one("#exec-args-json",    Static).update("")
        self._build_queue()

    # ── Logging ───────────────────────────────────────────────

    def _log(self, level: str, message: str) -> None:
        if not self._log_widget:
            return
        now   = datetime.datetime.now().strftime("%H:%M:%S")
        badge = _BADGES.get(level, _BADGES["INFO"])
        col   = _LOG_COL.get(level, _FG)
        self._log_widget.write(f"[{_DIM}]{now}[/]  {badge}  [{col}]{message}[/]")

    # ── Bindings ──────────────────────────────────────────────

    @work(exclusive=True)
    async def action_execute_step(self) -> None:
        if self.mode != "step":
            return
        session_id = getattr(self.app, "session_id", None)
        if not session_id or session_id == "OFFLINE" or not self.plan_id:
            return

        self._log("RUN", "Executing current step…")
        self.execution_active = True
        try:
            result      = await api.execute_plan(session_id, self.plan_id, mode="step")
            results     = result.get("results", [])
            last        = results[-1] if results else {}
            step_status = last.get("status", "unknown")
            output      = str(last.get("output") or last.get("error") or "")[:120]

            if step_status == "success":
                self._log("OK",  f"Step complete → {output}")
            else:
                self._log("ERR", f"Step failed   → {output}")

            # reload + advance
            await self._load_plan()
            self._current_idx += 1
            self._show_current_step()
        except Exception as e:
            self._log("ERR", f"Execution error: {e}")
        finally:
            self.execution_active = False

    @work(exclusive=True)
    async def action_skip_step(self) -> None:
        if self.mode != "step":
            return
        self._log("WARN", f"Skipping step {self._current_idx + 1}…")
        self._current_idx += 1
        if self._current_idx >= self._total_steps:
            self._show_all_done()
        else:
            self._show_current_step()

    def action_retry_step(self) -> None:
        self._log("INFO", "Retrying current step…")
        self._show_current_step()

    # ── Full mode execution ───────────────────────────────────

    @work
    async def start_full_execution(self) -> None:
        session_id = getattr(self.app, "session_id", None)
        self.execution_active = True
        try:
            result = await api.execute_plan(session_id, self.plan_id, mode="full")
            self.job_id = result.get("job_id")
            self._log("INFO", f"Job [{_BL}]{self.job_id}[/] queued — polling…")
            self.poll_execution_status()
        except Exception as e:
            self.execution_active = False
            self._log("ERR", f"Failed to start: {e}")

    @work
    async def poll_execution_status(self) -> None:
        session_id = getattr(self.app, "session_id", None)
        if not self.job_id:
            return
        start = asyncio.get_event_loop().time()
        while self.execution_active:
            try:
                data    = await api.get_execution_status(session_id, self.job_id)
                status  = data.get("status", "unknown")
                prog    = data.get("progress", "0%")
                elapsed = asyncio.get_event_loop().time() - start

                try:
                    pct_val = int(str(prog).replace("%",""))
                except Exception:
                    pct_val = 0
                fill = round(pct_val / 100 * 10)
                bar  = _progress_bar(fill, 10)

                self.query_one("#exec-step-label", Static).update(
                    f"[bold {_FG}]{status.upper()}  [{elapsed:.1f}s][/]"
                )
                self.query_one("#exec-bar", Static).update(bar)
                self.query_one("#exec-pct", Static).update(f"[bold {_BL}]{prog}[/]")

                err = data.get("error")
                if err:
                    self._log("ERR", str(err))

                if status in ("completed", "failed"):
                    self.execution_active = False
                    col = _GR if status == "completed" else _RD
                    self._log("OK" if status == "completed" else "ERR",
                              f"Execution {status.upper()}")
                    for r in data.get("results", []):
                        lvl = "OK" if r.get("status") == "success" else "ERR"
                        self._log(lvl,
                            f"[bold]{r.get('tool','?')}[/] – "
                            f"{str(r.get('output') or r.get('error',''))[:80]}"
                        )
                    break
                await asyncio.sleep(1.5)
            except Exception as e:
                self._log("WARN", f"Poll: {e}")
                await asyncio.sleep(2.0)
