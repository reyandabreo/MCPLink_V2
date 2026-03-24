from datetime import datetime

from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Vertical, Horizontal, ScrollableContainer, VerticalScroll
from textual.widgets import Static, Input
from textual.reactive import reactive
from textual import work
from textual import events

from cli.components.nav import TopMenu
from cli.api_client import api

# ── Tool classification ──────────────────────────────────────
_EXECUTION_EXACT: frozenset[str] = frozenset({
    "run_python", "execute_code",
    "git_commit", "init_git_repo",
    "move_file",
})
_RESTRICTED_SUBSTR = ("shell",)


def _tool_permission(name: str) -> tuple[str, str]:
    """Return (symbol, colour) for a tool name."""
    if any(s in name for s in _RESTRICTED_SUBSTR):
        return "✖", "#f7768e"
    if name in _EXECUTION_EXACT:
        return "⚠", "#e0af68"
    return "✔", "#9ece6a"


# ── Navigation categories ─────────────────────────────────────
_CATEGORIES = [
    ("##", "Execution Limits"),
    ("⚙",  "Agent Controls"),
    ("⌂",  "Workspace"),
    ("⚒",  "Tool Permissions"),
    ("≡",  "Logging"),
]


class PolicyScreen(Screen):
    """Policy Control Center — 3-column layout."""

    BINDINGS = [
        ("escape",  "blur_or_pop",  "Back"),
        ("e",       "toggle_edit",  "Edit"),
        ("ctrl+s",  "save_policy",  "Save"),
        ("r",       "reset_policy", "Reset"),
        ("up",      "category_prev", "Prev Category"),
        ("down",    "category_next", "Next Category"),
        ("1",       "show_cat_1",   "Execution Limits"),
        ("2",       "show_cat_2",   "Agent Controls"),
        ("3",       "show_cat_3",   "Workspace"),
        ("4",       "show_cat_4",   "Tool Permissions"),
        ("5",       "show_cat_5",   "Logging"),
    ]

    _edit_mode: reactive[bool] = reactive(False)
    _active_category: reactive[int] = reactive(0)
    _policy_data: dict = {}
    _policy_defaults: dict = {}
    _tools_data: dict = {}
    _tool_names: list[str] = []
    _session_data: dict = {}

    # ── helpers ──────────────────────────────────────────────

    @staticmethod
    def _fmt_time(iso_ts: str | None) -> str:
        if not iso_ts:
            return "—"
        try:
            return datetime.fromisoformat(iso_ts.replace("Z", "+00:00")).strftime("%H:%M:%S")
        except Exception:
            return "—"

    def _build_bar(self, value: float, width: int = 24) -> str:
        filled = int(value * width)
        filled = max(0, min(width, filled))
        return (
            f"[#e0af68]{'█' * filled}[/]"
            f"[#2a2e40]{'░' * (width - filled)}[/]"
        )

    def _build_sparkbar(self, values: list[int]) -> str:
        if not values:
            values = [0] * 8
        glyphs = "▁▂▃▄▅▆▇█"
        peak = max(values) if max(values) > 0 else 1
        chunks: list[str] = []
        for v in values[:12]:
            idx = min(7, round((v / peak) * 7))
            chunks.append(f"[#7aa2f7]{glyphs[idx]}[/]")
        return " ".join(chunks)

    def _risk_profile(self) -> tuple[float, str, str, str]:
        restricted = sum(1 for n in self._tool_names if _tool_permission(n)[0] == "✖")
        execution = sum(1 for n in self._tool_names if _tool_permission(n)[0] == "⚠")
        total = max(1, len(self._tool_names))
        ratio = ((restricted * 1.0) + (execution * 0.6)) / total
        if ratio >= 0.7:
            return 0.85, "High", "#f7768e", "Higher share of restricted/execution tools; enforce strict reviews."
        if ratio >= 0.4:
            return 0.65, "Medium", "#e0af68", "Mixed-risk tool set; monitor execution-capable tools closely."
        return 0.35, "Low", "#9ece6a", "Mostly low-risk tools; maintain standard policy checks."

    def _policy_rows_for_category(self) -> list[tuple[str, str]]:
        p = self._policy_data
        jobs = self._session_data.get("execution_jobs", {}) if isinstance(self._session_data, dict) else {}
        plans = self._session_data.get("plans", {}) if isinstance(self._session_data, dict) else {}
        completed_jobs = sum(1 for j in jobs.values() if j.get("status") == "completed")
        failed_jobs = sum(1 for j in jobs.values() if j.get("status") == "failed")

        if self._active_category == 0:
            return [
                ("Max File Size", f"{p.get('max_file_size_mb', '—')} MB"),
                ("Max Execution Time", f"{p.get('execution_timeout_seconds', '—')} s"),
                ("Tracked Plans", str(len(plans))),
                ("Execution Jobs", str(len(jobs))),
                ("Session Status", "ONLINE" if getattr(self.app, "session_id", None) not in (None, "OFFLINE") else "OFFLINE"),
                ("Policy Source", str(api.client.base_url)),
            ]

        if self._active_category == 1:
            session_id = getattr(self.app, "session_id", None)
            return [
                ("LLM Provider", str(p.get("llm_provider", "—")).upper()),
                ("Session", "ACTIVE" if session_id and session_id != "OFFLINE" else "OFFLINE"),
                ("Session ID", session_id[:8] if session_id and session_id != "OFFLINE" else "—"),
                ("Connected Tools", str(len(self._tool_names))),
                ("Completed Jobs", str(completed_jobs)),
                ("Failed Jobs", str(failed_jobs)),
            ]

        if self._active_category == 2:
            session_id = getattr(self.app, "session_id", None)
            sandbox_state = "ONLINE" if session_id and session_id != "OFFLINE" else "OFFLINE"
            max_upload = p.get("max_file_size_mb", "—")
            return [
                ("API Base", str(api.client.base_url)),
                ("Sandbox", sandbox_state),
                ("Upload Policy", f"MAX {max_upload} MB"),
                ("Allowed Tool Count", str(len(self._tool_names))),
                ("Execution Enabled", str(sum(1 for n in self._tool_names if _tool_permission(n)[0] == "⚠"))),
                ("Restricted Tools", str(sum(1 for n in self._tool_names if _tool_permission(n)[0] == "✖"))),
            ]

        if self._active_category == 3:
            allowed = sum(1 for n in self._tool_names if _tool_permission(n)[0] == "✔")
            execution = sum(1 for n in self._tool_names if _tool_permission(n)[0] == "⚠")
            restricted = sum(1 for n in self._tool_names if _tool_permission(n)[0] == "✖")
            return [
                ("Allowed", str(allowed)),
                ("Execution", str(execution)),
                ("Restricted", str(restricted)),
                ("Total Registered", str(len(self._tool_names))),
                ("Override Enabled", str(self._policy_data.get("override_count", 0))),
                ("Policy Mode", f"{str(p.get('llm_provider', 'runtime')).lower()}_policy"),
            ]

        last_plan_ts = None
        for plan in plans.values():
            ts = plan.get("created_at")
            if ts and (last_plan_ts is None or ts > last_plan_ts):
                last_plan_ts = ts
        return [
            ("Log Level", str(p.get("log_level", "—")).upper()),
            ("Execution Jobs", str(len(jobs))),
            ("Completed", str(completed_jobs)),
            ("Failed", str(failed_jobs)),
            ("Latest Activity", self._fmt_time(last_plan_ts)),
            ("Audit Stream", "ENABLED" if str(p.get("log_level", "INFO")).upper() != "OFF" else "DISABLED"),
        ]

    def _update_active_category_ui(self) -> None:
        self.query_one("#pol-cat-pos", Static).update(
            f"[dim #565f89]{self._active_category + 1:02d}/05[/]"
        )
        for i in range(len(_CATEGORIES)):
            node = self.query_one(f"#pol-nav-{i}", Static)
            if i == self._active_category:
                node.add_class("pol-nav-active")
            else:
                node.remove_class("pol-nav-active")

    def _update_inspector(self) -> None:
        title = _CATEGORIES[self._active_category][1]
        self.query_one("#pol-mid-meta", Static).update(
            f"[dim #565f89]section: {title.lower().replace(' ', '_')}[/]"
        )

        rows = self._policy_rows_for_category()
        for i in range(6):
            label, value = rows[i] if i < len(rows) else ("—", "—")
            self.query_one(f"#pol-lab-{i+1}", Static).update(label.upper())
            self.query_one(f"#pol-val-{i+1}", Static).update(f"[bold #2ac3de]{value}[/]")

        bar_value, score, score_col, summary = self._risk_profile()
        self.query_one("#pol-impact-score", Static).update(f"[bold {score_col}]{score}[/]")
        self.query_one("#pol-impact-bar", Static).update(self._build_bar(bar_value))
        self.query_one("#pol-impact-desc", Static).update(f"[dim italic]{summary}[/]")

    def _update_tool_access(self) -> None:
        container = self.query_one("#pol-tools-list")
        for child in list(container.children):
            child.remove()
        if not self._tool_names:
            container.mount(Static("  [dim #565f89]No tools registered[/]", classes="pol-tool-row"))
            return
        for name in sorted(self._tool_names):
            sym, col = _tool_permission(name)
            if sym == "✔":
                tag = "Permissive"
            elif sym == "⚠":
                tag = "Review Required"
            else:
                tag = "Blocked"
            container.mount(
                Static(
                    f"  [{col}]{sym}[/]  [#c0caf5]{name}[/]  [dim]{tag}[/]",
                    classes="pol-tool-row",
                )
            )

    def _update_traffic(self) -> None:
        jobs = self._session_data.get("execution_jobs", {}) if isinstance(self._session_data, dict) else {}
        plans = self._session_data.get("plans", {}) if isinstance(self._session_data, dict) else {}
        values: list[int] = []

        for job in jobs.values():
            results = job.get("results") or []
            values.append(len(results))

        if not values:
            values = [0] * 8

        while len(values) < 8:
            values.insert(0, 0)
        values = values[-8:]

        total_steps = sum(values)
        span_minutes = 1
        created = []
        for plan in plans.values():
            ts = plan.get("created_at")
            if ts:
                try:
                    created.append(datetime.fromisoformat(ts.replace("Z", "+00:00")))
                except Exception:
                    pass
        if len(created) >= 2:
            delta = (max(created) - min(created)).total_seconds() / 60
            span_minutes = max(1, int(delta))
        req_per_min = total_steps / span_minutes

        self.query_one("#pol-traffic-val", Static).update(f"[bold #2ac3de]{req_per_min:.1f} req/m[/]")
        self.query_one("#pol-sparkbar", Static).update(self._build_sparkbar(values))

    def _update_title(self) -> None:
        if self._edit_mode:
            self.query_one("#pol-mid-title", Static).update(
                " [bold #7aa2f7]POLICY INSPECTOR[/]  [bold #d29922 on #2d2000] EDIT MODE [/] "
            )
        else:
            self.query_one("#pol-mid-title", Static).update(
                " [bold #7aa2f7]POLICY INSPECTOR[/]  [bold #9ece6a on #1c2a1c] ACTIVE [/] "
            )

    def _toggle_edit(self, on: bool | None = None) -> None:
        if on is None:
            on = not self._edit_mode
        self._edit_mode = on

        view = self.query_one("#pol-view-content")
        edit = self.query_one("#pol-edit-panel")

        if on:
            view.add_class("hidden")
            edit.remove_class("hidden")
            p = self._policy_data
            self.query_one("#pol-size",     Input).value = str(p.get("max_file_size_mb", ""))
            self.query_one("#pol-timeout",  Input).value = str(p.get("execution_timeout_seconds", ""))
            self.query_one("#pol-log",      Input).value = str(p.get("log_level", ""))
            self.query_one("#pol-provider", Input).value = str(p.get("llm_provider", "gemini"))
            self.query_one("#pol-size",     Input).focus()
        else:
            edit.add_class("hidden")
            view.remove_class("hidden")
            self.query_one("#pol-edit-status", Static).update("")

        self._update_title()

    # ── compose ──────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield TopMenu(active_tab="Policy")

        with Horizontal(id="policy-3col"):

            # ── LEFT: Categories ─────────────────────────────
            with Vertical(id="pol-left"):
                with Horizontal(classes="pol-panel-header"):
                    yield Static("[bold #7aa2f7]≡≡ CATEGORIES[/]", classes="pol-header-title")
                    yield Static("[dim #565f89]01/05[/]", id="pol-cat-pos", classes="pol-header-right")
                with Vertical(id="pol-nav-list"):
                    for i, (icon, label) in enumerate(_CATEGORIES):
                        active = " pol-nav-active" if i == 0 else ""
                        yield Static(
                            f"  [#7aa2f7]{icon}[/]  {label}",
                            id=f"pol-nav-{i}",
                            classes=f"pol-nav-item{active}",
                        )
                with Vertical(id="pol-profile-footer"):
                    yield Static("[bold #7aa2f7]ACTIVE PROFILE[/]", classes="pol-profile-label")
                    yield Static("loading-policy", id="pol-profile-value", classes="pol-profile-value")

            # ── MIDDLE: Policy Inspector ──────────────────────
            with Vertical(id="pol-middle"):
                with Horizontal(classes="pol-panel-header"):
                    yield Static(
                        " [bold #7aa2f7]POLICY INSPECTOR[/]  [bold #9ece6a on #1c2a1c] ACTIVE [/] ",
                        id="pol-mid-title",
                        classes="pol-header-title",
                    )
                    yield Static("[dim #565f89]section: execution_limits[/]", id="pol-mid-meta", classes="pol-header-right")

                # ── view mode ────────────────────────────────
                with VerticalScroll(id="pol-view-content"):
                    with Horizontal(classes="pol-grid-row"):
                        with Vertical(classes="pol-grid-cell"):
                            yield Static("—", id="pol-lab-1", classes="pol-field-label")
                            yield Static("[bold #2ac3de]—[/]", id="pol-val-1", classes="pol-field-value")
                        with Vertical(classes="pol-grid-cell"):
                            yield Static("—", id="pol-lab-2", classes="pol-field-label")
                            yield Static("[bold #2ac3de]—[/]", id="pol-val-2", classes="pol-field-value")
                    with Horizontal(classes="pol-grid-row"):
                        with Vertical(classes="pol-grid-cell"):
                            yield Static("—", id="pol-lab-3", classes="pol-field-label")
                            yield Static("[bold #2ac3de]—[/]", id="pol-val-3", classes="pol-field-value")
                        with Vertical(classes="pol-grid-cell"):
                            yield Static("—", id="pol-lab-4", classes="pol-field-label")
                            yield Static("[bold #2ac3de]—[/]", id="pol-val-4", classes="pol-field-value")
                    with Horizontal(classes="pol-grid-row"):
                        with Vertical(classes="pol-grid-cell"):
                            yield Static("—", id="pol-lab-5", classes="pol-field-label")
                            yield Static("[bold #2ac3de]—[/]", id="pol-val-5", classes="pol-field-value")
                        with Vertical(classes="pol-grid-cell"):
                            yield Static("—", id="pol-lab-6", classes="pol-field-label")
                            yield Static("[bold #2ac3de]—[/]", id="pol-val-6", classes="pol-field-value")

                    # impact card
                    with Vertical(id="pol-impact-card"):
                        yield Static(
                            "[#e0af68]▣[/] [bold #c0caf5]Policy Impact Assessment[/]",
                            id="pol-impact-title",
                        )
                        with Horizontal(classes="pol-impact-metric-row"):
                            yield Static("Execution Safety", classes="pol-impact-label")
                            yield Static("[bold #e0af68]Medium[/]", id="pol-impact-score", classes="pol-impact-value")
                        yield Static("", id="pol-impact-bar", classes="pol-impact-bar-row")
                        yield Static(
                            "[dim italic]This policy allows script execution which increases"
                            " potential attack surface. Monitor shell_exec usage frequently.[/]",
                            id="pol-impact-desc",
                        )

                # ── edit mode (hidden by default) ─────────────
                with ScrollableContainer(id="pol-edit-panel", classes="hidden"):
                    for section_title, fields in [
                        ("Execution Limits", [
                            ("Max File Size (MB)",     "pol-size",     "e.g. 10"),
                            ("Max Execution Time (s)", "pol-timeout",  "e.g. 30"),
                        ]),
                        ("Agent Controls", [
                            ("LLM Provider",           "pol-provider", "gemini / openai"),
                        ]),
                        ("Logging", [
                            ("Log Level",              "pol-log",      "INFO / DEBUG / WARNING"),
                        ]),
                    ]:
                        yield Static(f"[bold #7aa2f7]{section_title}[/]", classes="pol-edit-section")
                        for label, wid, ph in fields:
                            with Horizontal(classes="pol-input-row"):
                                yield Static(f"[#7d8590]{label}[/]", classes="pol-input-label")
                                yield Input(id=wid, placeholder=ph, classes="pol-input")
                    yield Static("", id="pol-edit-status")

                yield Static("", id="policy-status")

            # ── RIGHT: Tool Access ───────────────────────────
            with Vertical(id="pol-right"):
                with Horizontal(classes="pol-panel-header"):
                    yield Static("[bold #7aa2f7]TOOL ACCESS[/]", classes="pol-header-title")
                    yield Static("[dim #565f89]≡[/]", classes="pol-header-right")
                yield Static(
                    " [#9ece6a]✔[/] [dim]Allowed[/]   "
                    "[#e0af68]⚠[/] [dim]Execution[/]   "
                    "[#f7768e]✖[/] [dim]Restricted[/]",
                    id="pol-legend-row",
                )
                with VerticalScroll(id="pol-tools-list"):
                    yield Static("  [dim #565f89]loading…[/]", id="pol-tools-loading")
                with Vertical(id="pol-traffic-footer"):
                    with Horizontal(classes="pol-traffic-head-row"):
                        yield Static("[dim #565f89]TRAFFIC VOLUME[/]", classes="pol-traffic-lbl")
                        yield Static("[bold #2ac3de]-- req/m[/]", id="pol-traffic-val", classes="pol-traffic-val")
                    yield Static("", id="pol-sparkbar")

        yield Static(
            "  [bold #0f111a on #7aa2f7] E [/] [dim]Edit Policy[/]"
            "   [bold #0f111a on #7aa2f7] S [/] [dim]Save Changes[/]"
            "   [bold #0f111a on #7aa2f7] R [/] [dim]Reset[/]"
            "   [bold #0f111a on #7aa2f7] ↑↓ [/] [dim]Category[/]"
            "   [bold #0f111a on #565f89] Esc [/] [dim]Back[/]"
            "   [#414868]│[/]  [dim italic]Connecting...[/]",
            id="pol-hotkey",
            classes="pol-hotkey-bar",
        )

    # ── lifecycle ─────────────────────────────────────────────

    async def on_mount(self) -> None:
        session_id = getattr(self.app, "session_id", None)
        sess_info = self.query_one("#chip-sess", Static)
        if session_id and session_id != "OFFLINE":
            sess_info.update(f" [bold #9ECE6A]●[/] [#9ECE6A]SESSION:[/] [bold #C0CAF5]{session_id[:8]}[/] ")
        else:
            sess_info.update(" [bold #F7768E]●[/] [#F7768E]SESSION:[/] [bold #F7768E]OFFLINE[/] ")

        self._update_active_category_ui()
        self._update_title()
        host = str(api.client.base_url)
        self.query_one("#pol-hotkey", Static).update(
            "  [bold #0f111a on #7aa2f7] E [/] [dim]Edit Policy[/]"
            "   [bold #0f111a on #7aa2f7] S [/] [dim]Save Changes[/]"
            "   [bold #0f111a on #7aa2f7] R [/] [dim]Reset[/]"
            "   [bold #0f111a on #7aa2f7] ↑↓ [/] [dim]Category[/]"
            "   [bold #0f111a on #565f89] Esc [/] [dim]Back[/]"
            f"   [#414868]│[/]  [dim italic]Connected to {host}[/]"
        )
        self.fetch_policy()

    def update_status(self) -> None:
        pass

    # ── data fetching ──────────────────────────────────────────

    @work(exclusive=True)
    async def fetch_policy(self) -> None:
        try:
            policy = await api.get_policy()
            self._policy_data = dict(policy)
            if not self._policy_defaults:
                self._policy_defaults = dict(policy)
        except Exception:
            self._policy_data = {}
        try:
            tools = await api.get_tools()
            self._tools_data = dict(tools) if isinstance(tools, dict) else {}
            self._tool_names = list(tools) if tools else []
        except Exception:
            self._tools_data = {}
            self._tool_names = []

        session_id = getattr(self.app, "session_id", None)
        if session_id and session_id != "OFFLINE":
            try:
                self._session_data = await api.get_session(session_id)
            except Exception:
                self._session_data = {}
        else:
            self._session_data = {}

        provider = str(self._policy_data.get("llm_provider", "runtime")).lower()
        self.query_one("#pol-profile-value", Static).update(f"{provider}_policy")

        self._update_active_category_ui()
        self._update_inspector()
        self._update_tool_access()
        self._update_traffic()

    # ── actions ──────────────────────────────────────────────

    def action_blur_or_pop(self) -> None:
        if isinstance(self.focused, Input):
            self.set_focus(None)
        elif self._edit_mode:
            self._toggle_edit(False)
        else:
            self.app.pop_screen()

    def action_toggle_edit(self) -> None:
        self._toggle_edit()

    def _set_category(self, index: int) -> None:
        self._active_category = max(0, min(len(_CATEGORIES) - 1, index))
        self._update_active_category_ui()
        self._update_inspector()

    def action_show_cat_1(self) -> None:
        self._set_category(0)

    def action_show_cat_2(self) -> None:
        self._set_category(1)

    def action_show_cat_3(self) -> None:
        self._set_category(2)

    def action_show_cat_4(self) -> None:
        self._set_category(3)

    def action_show_cat_5(self) -> None:
        self._set_category(4)

    def action_category_prev(self) -> None:
        if isinstance(self.focused, Input):
            return
        self._set_category(self._active_category - 1)

    def action_category_next(self) -> None:
        if isinstance(self.focused, Input):
            return
        self._set_category(self._active_category + 1)

    def on_click(self, event: events.Click) -> None:
        wid = getattr(event.widget, "id", "") or ""
        if wid.startswith("pol-nav-"):
            try:
                idx = int(wid.split("-")[-1])
                self._set_category(idx)
            except Exception:
                return

    def _flash_status(self, msg: str) -> None:
        w = self.query_one("#policy-status", Static)
        w.update(msg)
        self.set_timer(3, lambda: w.update(""))

    @work(exclusive=True)
    async def action_save_policy(self) -> None:
        if not self._edit_mode:
            self._toggle_edit(True)
            return

        size_raw     = self.query_one("#pol-size",     Input).value.strip()
        timeout_raw  = self.query_one("#pol-timeout",  Input).value.strip()
        log_raw      = self.query_one("#pol-log",      Input).value.strip()
        provider_raw = self.query_one("#pol-provider", Input).value.strip().lower()

        updates: dict = {}
        if size_raw.isdigit():
            updates["max_file_size_mb"] = int(size_raw)
        if timeout_raw.isdigit():
            updates["execution_timeout_seconds"] = int(timeout_raw)
        if log_raw:
            updates["log_level"] = log_raw.upper()
        if provider_raw in ("gemini", "openai"):
            updates["llm_provider"] = provider_raw
        elif provider_raw:
            self.query_one("#pol-edit-status", Static).update(
                "[#f7768e]⚠  LLM Provider must be 'gemini' or 'openai'.[/]"
            )
            return

        if not updates:
            self.query_one("#pol-edit-status", Static).update(
                "[#e0af68]⚠  No valid changes to save.[/]"
            )
            return

        try:
            await api.update_policy(updates)
            self._policy_data.update(updates)
            self._toggle_edit(False)
            self._flash_status("[bold #9ece6a]✔  Policy updated successfully.[/]")
            self.fetch_policy()
        except Exception as e:
            self.query_one("#pol-edit-status", Static).update(
                f"[#f7768e]✖  Failed to save: {e}[/]"
            )

    @work(exclusive=True)
    async def action_reset_policy(self) -> None:
        defaults = self._policy_defaults or {
            "max_file_size_mb":          self._policy_data.get("max_file_size_mb", 10),
            "execution_timeout_seconds": self._policy_data.get("execution_timeout_seconds", 30),
            "log_level":                 self._policy_data.get("log_level", "INFO"),
            "llm_provider":              self._policy_data.get("llm_provider", "gemini"),
        }
        try:
            await api.update_policy(defaults)
            self._policy_data.update(defaults)
            if self._edit_mode:
                self._toggle_edit(False)
            self._flash_status("[bold #9ece6a]✔  Policy reset to defaults.[/]")
            self.fetch_policy()
        except Exception as e:
            self._flash_status(f"[#f7768e]✖  Reset failed: {e}[/]")
