from rich.text import Text
from datetime import datetime

from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Container, VerticalScroll, Horizontal, Vertical
from textual.widgets import Static, DataTable
from textual import work

from cli.components.nav import TopMenu, get_shortcut_str
from cli.api_client import api

# Tool names that are restricted by default (heuristic)
_RESTRICTED_IF_CONTAINS = ("shell",)
_RESTRICTED_EXACT = frozenset({"run_shell", "shell_exec", "bash_exec"})
_EXECUTION_EXACT  = frozenset({
    "run_python", "execute_code",
    "git_commit", "init_git_repo",
    "generate_tests", "summarize_document",
    "move_file", "format_code",
    "edit_docx_sections",
})

# Tokyo Night Colors
_BL = "#7aa2f7"  # Blue
_CY = "#2ac3de"  # Cyan
_GR = "#9ece6a"  # Green
_YL = "#e0af68"  # Yellow
_RD = "#f85149"  # Red
_PU = "#bb9af7"  # Purple
_FG = "#c0caf5"  # Foreground
_BG = "#0f111a"  # Background


class ToolsScreen(Screen):
    """Tool Registry with 3-column professional layout."""

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("r",      "action_refresh_tools", "Refresh"),
        ("e",      "action_toggle_tool",   "Toggle Policy"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.raw_tools: dict = {}
        self._tool_rows: list[str] = []
        self._selected_tool: str = ""
        self._local_overrides: set[str] = set()
        self._exec_count: int = 0
        self._last_used: str = "—"

    @staticmethod
    def _fmt_iso_to_hms(ts: str | None) -> str:
        if not ts:
            return "—"
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%H:%M:%S")
        except Exception:
            return "—"

    # ──────────────────────────────── helpers ─────────────────────────────────

    def _is_restricted_by_default(self, name: str) -> bool:
        return (
            any(kw in name for kw in _RESTRICTED_IF_CONTAINS)
            or name in _RESTRICTED_EXACT
        )

    def _tool_status(self, name: str) -> tuple[str, str]:
        """Return (kind_key, detail_markup)."""
        restricted = self._is_restricted_by_default(name)
        overridden = name in self._local_overrides

        if restricted and overridden:
            return ("override",   f"[bold {_YL}]⚡ Enabled (Override)[/]")
        elif restricted:
            return ("restricted", f"[bold {_RD}]✖ Restricted[/]")
        elif name in _EXECUTION_EXACT:
            return ("execution",  f"[bold {_YL}]⚠ Execution[/]")
        else:
            return ("allowed",    f"[bold {_GR}]✔ Allowed[/]")

    @staticmethod
    def _status_cell(kind: str) -> Text:
        """Rich Text cell — symbol only."""
        if kind == "restricted":
            return Text("✖", style=f"bold {_RD}")
        if kind == "override":
            return Text("⚡", style=f"bold {_YL}")
        if kind == "execution":
            return Text("⚠", style=f"bold {_YL}")
        return Text("✔", style=f"bold {_GR}")

    def _get_tool_id(self, name: str) -> str:
        """Generate tool ID from index."""
        if name in self._tool_rows:
            idx = self._tool_rows.index(name)
            return f"tool_{idx:02d}"
        return "tool_00"

    # ──────────────────────────────── compose ─────────────────────────────────

    def compose(self) -> ComposeResult:
        yield TopMenu(active_tab="TOOLS")

        # Main container with 3-column layout
        with Container(id="tools-main-container"):
            with Horizontal(id="tools-body"):
                # Left: Tool Registry Table
                with Vertical(id="tools-left-panel"):
                    with Horizontal(id="tools-registry-header"):
                        yield Static(
                            "[bold #7aa2f7]◧[/] [bold #c0caf5]REGISTRY[/]",
                            id="tools-registry-title",
                        )
                        yield Static(
                            "[dim]COUNT: 0[/]",
                            id="tools-registry-count",
                        )
                    yield DataTable(
                        id="tools-registry-table",
                        cursor_type="row",
                        zebra_stripes=False,
                    )

                # Center: Tool Inspector with detailed sections
                with VerticalScroll(id="tools-inspector-panel"):
                    # Inspector Header
                    with Horizontal(id="tools-inspector-header"):
                        yield Static(
                            "[dim]INSPECTOR:[/] [bold #c0caf5]—[/]",
                            id="tools-inspector-title",
                        )
                        yield Static(
                            "[dim]ID:[/] [bold #7aa2f7]—[/]",
                            id="tools-inspector-id",
                        )
                    
                    # Description Section
                    yield Static("[dim]DESCRIPTION[/]", id="tools-desc-label")
                    yield Static(
                        "Select a tool from the registry to inspect details.",
                        id="tools-desc-box",
                    )
                    
                    # Policy and Status - side by side
                    with Horizontal(id="tools-policy-status-row"):
                        with Vertical(id="tools-policy-col"):
                            yield Static("[dim]POLICY[/]", id="tools-policy-label")
                            yield Static(
                                "[dim]—[/]",
                                id="tools-policy-badge",
                            )
                        with Vertical(id="tools-status-col"):
                            yield Static("[dim]STATUS[/]", id="tools-status-label")
                            yield Static(
                                "[dim]—[/]",
                                id="tools-status-badge",
                            )
                    
                    # Arguments Section
                    yield Static("[dim]ARGUMENTS[/]", id="tools-args-label")
                    yield Static(
                        "[dim]No tool selected.[/]",
                        id="tools-args-box",
                    )
                    
                    # Capabilities Section
                    yield Static("[dim]CAPABILITIES[/]", id="tools-caps-label")
                    yield Static(
                        "[dim]—[/]",
                        id="tools-caps-list",
                    )
                    
                    # Metadata Section
                    yield Static("[dim]METADATA[/]", id="tools-meta-label")
                    with Horizontal(id="tools-meta-row"):
                        yield Static("[dim]VERSION[/]\n[bold #c0caf5]—[/]", id="tools-meta-version")
                        yield Static("[dim]AUTHOR[/]\n[bold #c0caf5]—[/]", id="tools-meta-author")
                        yield Static("[dim]SANDBOX[/]\n[bold #c0caf5]—[/]", id="tools-meta-sandbox")
                    
                    # Toolbar
                    yield Static(
                        "[dim]⠿  ✎  ⬇  ⌕  ⚙  📦[/]",
                        id="tools-inspector-toolbar",
                    )

                # Right: Metrics Panel
                with VerticalScroll(id="tools-metrics-panel"):
                    yield Static(
                        "[bold #2ac3de]⚙[/] Metrics",
                        id="tools-metrics-header",
                    )
                    with Vertical(id="tools-metrics-body"):
                        with Vertical(classes="tools-metric-card"):
                            yield Static("[dim]TOTAL EXECUTIONS[/]", classes="tools-metric-label")
                            yield Static("[bold #c0caf5]0[/]", id="tools-metric-total", classes="tools-metric-value tools-metric-value-large")

                        with Vertical(classes="tools-metric-card"):
                            yield Static("[dim]LAST USED[/]", classes="tools-metric-label")
                            yield Static("[bold #2ac3de]—[/]", id="tools-metric-last-used", classes="tools-metric-value tools-metric-value-accent")

                        with Vertical(classes="tools-metric-card"):
                            yield Static("[dim]RISK SCORE[/]", classes="tools-metric-label")
                            with Horizontal(id="tools-risk-row"):
                                yield Static("[bold #e0af68]Medium[/]", id="tools-metric-risk-text", classes="tools-metric-value tools-metric-risk-text")
                                yield Static("[bold #e0af68]█████████[/][#414868]███████████[/]", id="tools-metric-risk-bar")

                        yield Static("[dim]DEPENDENCIES[/]", id="tools-deps-label")
                        with Vertical(id="tools-deps-list"):
                            yield Static("[dim]No dependency metadata available.[/]", id="tools-deps-empty")

        # Footer with hotkeys
        yield Static(
            f"[dim]↑↓[/dim] Navigate  "
            f"[dim]Enter[/dim] Inspect  "
            f"[dim]E[/dim] Toggle Policy  "
            f"[dim]R[/dim] Refresh  "
            f"[dim]/[/dim] Search  "
            f"[dim]Esc[/dim] Back",
            id="tools-footer",
        )

    # ──────────────────────────────── mount ───────────────────────────────────

    async def on_mount(self) -> None:
        tbl = self.query_one("#tools-registry-table", DataTable)
        tbl.add_column("#", width=3, key="num")
        tbl.add_column("TOOL NAME", width=24, key="name")
        tbl.add_column("STATUS", width=20, key="status")
        self.fetch_tools()

    # ──────────────────────────────── worker ──────────────────────────────────

    @work(exclusive=True)
    async def fetch_tools(self) -> None:
        try:
            self.raw_tools = await api.get_tools()
        except Exception as e:
            self.raw_tools = {}
            self._tool_rows = []
            self.query_one("#tools-registry-count", Static).update("[dim]COUNT: 0[/]")
            self.query_one("#tools-desc-box", Static).update(
                f"[{_RD}]Failed to load tools: {e}[/]"
            )
            await self._refresh_metrics()
            return

        self._tool_rows = list(self.raw_tools.keys())
        self.query_one("#tools-registry-count", Static).update(
            f"[dim]COUNT: {len(self._tool_rows)}[/]"
        )
        tbl = self.query_one("#tools-registry-table", DataTable)
        tbl.clear()

        for i, name in enumerate(self._tool_rows):
            kind, _ = self._tool_status(name)
            tbl.add_row(f"{i:02d}", name, self._status_cell(kind), key=name)

        await self._refresh_metrics()

        if self._tool_rows:
            self._select_tool(self._tool_rows[0])
            tbl.cursor_location = (0, 0)

    async def _refresh_metrics(self) -> None:
        session_id = getattr(self.app, "session_id", None)
        if not session_id or session_id == "OFFLINE":
            self._exec_count = 0
            self._last_used = "OFFLINE"
            self.query_one("#tools-metric-total", Static).update(f"[bold {_FG}]0[/]")
            self.query_one("#tools-metric-last-used", Static).update(f"[bold {_CY}]OFFLINE[/]")
            return

        try:
            session = await api.get_session(session_id)
            jobs = session.get("execution_jobs", {})
            plans = session.get("plans", {})

            total_steps = sum(len(job.get("results", [])) for job in jobs.values())
            self._exec_count = total_steps if total_steps > 0 else len(jobs)

            latest_plan_ts = None
            for plan in plans.values():
                ts = plan.get("created_at")
                if ts and (latest_plan_ts is None or ts > latest_plan_ts):
                    latest_plan_ts = ts
            self._last_used = self._fmt_iso_to_hms(latest_plan_ts)
        except Exception:
            self._exec_count = 0
            self._last_used = "—"

        self.query_one("#tools-metric-total", Static).update(
            f"[bold {_FG}]{self._exec_count}[/]"
        )
        self.query_one("#tools-metric-last-used", Static).update(
            f"[bold {_CY}]{self._last_used}[/]"
        )

    # ──────────────────────────────── events ──────────────────────────────────

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key and event.row_key.value is not None:
            self._select_tool(str(event.row_key.value))

    # ──────────────────────────────── logic ───────────────────────────────────

    def _select_tool(self, name: str) -> None:
        """Display tool details in the inspector sections and metrics panel."""
        self._selected_tool = name
        tool_data = self.raw_tools.get(name, {})
        props = tool_data.get("parameters", {}).get("properties", {})
        required = set(tool_data.get("parameters", {}).get("required", []))
        meta = tool_data.get("metadata") if isinstance(tool_data.get("metadata"), dict) else {}

        self.query_one("#tools-inspector-title", Static).update(
            f"[dim]INSPECTOR:[/] [bold {_FG}]{name.upper()}[/]"
        )
        self.query_one("#tools-inspector-id", Static).update(
            f"[dim]ID:[/] [bold {_BL}]{self._get_tool_id(name)}[/]"
        )
        self.query_one("#tools-desc-box", Static).update(
            tool_data.get("description", "No description available.")
        )

        restricted = self._is_restricted_by_default(name)
        overridden = name in self._local_overrides
        if restricted and overridden:
            policy_text = "⚡ Enabled (Override)"
            policy_style = _YL
        elif restricted:
            policy_text = "✖ Restricted"
            policy_style = _RD
        elif name in _EXECUTION_EXACT:
            policy_text = "⚠ Execution (Approval Required)"
            policy_style = _YL
        else:
            policy_text = "✔ Allowed"
            policy_style = _GR

        self.query_one("#tools-policy-badge", Static).update(
            f"[bold {policy_style}]{policy_text}[/]"
        )
        self.query_one("#tools-status-badge", Static).update(
            f"[bold {_GR}]✔ Registered[/]"
        )

        argument_lines: list[str] = []
        if props:
            for arg_name, schema in props.items():
                arg_type = schema.get("type", "any")
                suffix = "required" if arg_name in required else "optional"
                description = schema.get("description")
                if not arg_name in required and schema.get("default") is not None:
                    suffix = f"optional, def: {schema['default']}"
                elif not arg_name in required and arg_name == "timeout":
                    suffix = "optional, def: 30"
                argument_lines.append(
                    f"[{_CY}]{arg_name}[/]    [dim]{arg_type} ({suffix})[/]"
                )
                if description:
                    argument_lines.append(f"[dim]{description}[/]")
        else:
            argument_lines.append("[dim]No arguments.[/dim]")
        self.query_one("#tools-args-box", Static).update("\n".join(argument_lines))

        capabilities = tool_data.get("capabilities")
        if not capabilities:
            caps: list[str] = ["Schema Validated"]
            prop_names = [k.lower() for k in props.keys()]
            if any(k in p for p in prop_names for k in ("path", "file", "dir")):
                caps.append("File System")
            if any(k in p for p in prop_names for k in ("url", "web", "http", "endpoint")):
                caps.append("Network")
            if any(k in p for p in prop_names for k in ("code", "script", "command")):
                caps.append("Execution")
            capabilities = caps
        self.query_one("#tools-caps-list", Static).update(
            "  ".join(f"[bold #414868]{cap}[/]" for cap in capabilities)
        )

        deps_widget = self.query_one("#tools-deps-list", Vertical)
        for child in list(deps_widget.children):
            child.remove()
        dependencies = tool_data.get("dependencies")
        if isinstance(dependencies, list) and dependencies:
            for dep in dependencies[:6]:
                if isinstance(dep, dict):
                    dep_name = str(dep.get("name", "unknown"))
                    dep_ver = str(dep.get("version", "—"))
                else:
                    dep_name = str(dep)
                    dep_ver = "—"
                deps_widget.mount(
                    Static(
                        f"[bold #7aa2f7]◫[/] {dep_name} [dim]{dep_ver}[/]",
                        classes="tools-dependency-row",
                    )
                )
        else:
            deps_widget.mount(Static("[dim]No dependency metadata available.[/]", classes="tools-dependency-row"))

        version = meta.get("version") or tool_data.get("version") or "—"
        author = meta.get("author") or tool_data.get("author") or "Registry"
        sandbox_text = "ENABLED" if not restricted or overridden else "RESTRICTED"
        sandbox_col = _GR if sandbox_text == "ENABLED" else _RD
        self.query_one("#tools-meta-version", Static).update(
            f"[dim]VERSION[/]\n[bold {_FG}]{version}[/]"
        )
        self.query_one("#tools-meta-author", Static).update(
            f"[dim]AUTHOR[/]\n[bold {_FG}]{author}[/]"
        )
        self.query_one("#tools-meta-sandbox", Static).update(
            f"[dim]SANDBOX[/]\n[bold {sandbox_col}]{sandbox_text}[/]"
        )

        if restricted and not overridden:
            risk_pct, risk_text, risk_col = 85, "High", _RD
        elif name in _EXECUTION_EXACT:
            risk_pct, risk_text, risk_col = 65, "Medium", _YL
        else:
            risk_pct, risk_text, risk_col = 25, "Low", _GR
        filled = max(1, min(20, round(risk_pct / 5)))
        self.query_one("#tools-metric-total", Static).update(f"[bold {_FG}]{self._exec_count}[/]")
        self.query_one("#tools-metric-last-used", Static).update(f"[bold {_CY}]{self._last_used}[/]")
        self.query_one("#tools-metric-risk-text", Static).update(f"[bold {risk_col}]{risk_text}[/]")
        self.query_one("#tools-metric-risk-bar", Static).update(
            f"[bold {risk_col}]{'█' * filled}[/][#414868]{'█' * (20 - filled)}[/]"
        )

    # ──────────────────────────────── actions ─────────────────────────────────

    def action_toggle_tool(self) -> None:
        name = self._selected_tool
        if not name:
            return

        if not self._is_restricted_by_default(name):
            return

        if name in self._local_overrides:
            self._local_overrides.discard(name)
        else:
            self._local_overrides.add(name)

        kind, _ = self._tool_status(name)
        tbl = self.query_one("#tools-registry-table", DataTable)
        tbl.update_cell(name, "status", self._status_cell(kind), update_width=False)
        self._select_tool(name)

    def action_refresh_tools(self) -> None:
        self.fetch_tools()
