"""
Plans screen — matches the HTML reference design exactly:
  • Left panel  (builder form): labeled inputs, > prompt prefix, action buttons
  • Right panel (plan summary): 2×2 stat grid + metadata rows
  • Bottom section: Execution Pipeline step cards
"""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Container, Vertical, Horizontal, VerticalScroll
from textual.widgets import Static, Input, Select, TextArea
from textual import work

from cli.components.nav import TopMenu
from cli.api_client import api

# ── colour aliases ─────────────────────────────────────────────
_BL  = "#7AA2F7"   # primary blue accent
_DIM = "#565F89"   # muted dim
_GR  = "#9ECE6A"   # green
_YL  = "#E0AF68"   # yellow
_RD  = "#F7768E"   # red
_PU  = "#BB9AF7"   # purple
_FG  = "#C0CAF5"   # foreground
_BG  = "#0F111A"   # background

# ── helpers ────────────────────────────────────────────────────

def _allowed_badge(allowed: bool, tool: str) -> str:
    if not allowed:
        return f"[bold black on {_RD}]  ✖ RESTRICTED  [/]"
    if tool in ("run_python", "execute_code", "git_commit"):
        return f"[bold black on {_YL}]  ⚠ EXECUTION  [/]"
    if "exec" in tool or "shell" in tool:
        return f"[bold black on {_RD}]  ✖ SHELL BLOCKED  [/]"
    return f"[bold black on {_GR}]  ✔ ALLOWED  [/]"

def _badge_color(badge: str) -> str:
    if "ALLOWED" in badge:  return _GR
    if "EXECUTION" in badge: return _YL
    return _RD

def _fmt_args(args: dict) -> str:
    lines = []
    for k, v in list(args.items())[:4]:
        val = str(v)[:52] + ("…" if len(str(v)) > 52 else "")
        lines.append(f"[{_DIM}]│ {k}:[/] [{_FG}]{val}[/]")
    if not lines:
        lines.append(f"[{_DIM}]│ (no arguments)[/]")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
#  PLAN CREATION  (builder + live summary + pipeline cards)
# ══════════════════════════════════════════════════════════════

class PlanCreationScreen(Screen):
    BINDINGS = [
        ("ctrl+g", "generate_plan", "Generate"),
        ("escape", "blur_or_pop",   "Back"),
        ("ctrl+r", "reset_form",    "Reset"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._plan_data: dict = {}
        self._generating  = False

    # ── Layout ────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield TopMenu(active_tab="Plans")

        with Container(id="main-container"):
            with VerticalScroll(id="plans-scroll"):

                # ── TOP SPLIT ──────────────────────────────────
                with Horizontal(id="plans-top-split"):

                    # LEFT — Builder form
                    with Vertical(id="plan-builder-panel"):
                        # Panel header
                        yield Static(
                            f"  [{_BL}]──[/] [bold {_BL}]PLAN BUILDER[/] [{_BL}]──[/]"
                            f"[{_DIM}]                         [MODE: INSERT][/]",
                            id="builder-header",
                        )

                        # 1. Prompt
                        yield Static(f"[{_DIM}]1. PROMPT[/]", classes="plan-field-label")
                        with Horizontal(classes="plan-input-row", id="row-prompt"):
                            yield Static(f"[bold {_BL}] > [/]", classes="plan-input-prefix")
                            yield TextArea(
                                "",
                                placeholder="Describe your goal here…",
                                id="plan-prompt",
                                classes="plan-field-input plan-prompt-input",
                            )
                            yield Static(f"[{_DIM}] ⌘ [/]", classes="plan-input-suffix")

                        # 2. Document context
                        yield Static(f"[{_DIM}]2. DOCUMENT CONTEXT[/]", classes="plan-field-label")
                        with Horizontal(classes="plan-input-row", id="row-context"):
                            yield Static(f"[bold {_BL}] > [/]", classes="plan-input-prefix")
                            yield Input(
                                placeholder="Path to docs (optional)…",
                                id="plan-context",
                                classes="plan-field-input",
                            )
                            yield Static(f"[{_DIM}] 📄 [/]", classes="plan-input-suffix")

                        # 3. Execution mode
                        yield Static(f"[{_DIM}]3. EXECUTION MODE[/]", classes="plan-field-label")
                        with Horizontal(classes="plan-input-row", id="row-mode"):
                            yield Static(f"[bold {_GR}] > [/]", classes="plan-input-prefix")
                            yield Select(
                                [("safe", "safe"), ("step-by-step", "step"), ("aggressive", "aggressive")],
                                value="safe",
                                id="plan-mode-select",
                                classes="plan-field-input",
                            )
                            yield Static(f"[{_DIM}] 🔒 [/]", classes="plan-input-suffix")

                        yield Static("", id="plan-gen-status", classes="plan-status-row")

                        # Action buttons row
                        with Horizontal(id="plan-btn-row"):
                            yield Static(
                                f"[{_DIM}] RESET [/][bold {_FG}][Esc][/]",
                                id="btn-reset",
                                classes="plan-btn plan-btn-secondary",
                            )
                            yield Static(
                                f"[bold {_BG}] GENERATE PLAN [/][bold {_FG}][Ctrl+G][/]",
                                id="btn-generate",
                                classes="plan-btn plan-btn-primary",
                            )

                    # RIGHT — Plan Summary
                    with Vertical(id="plan-summary-panel"):
                        yield Static(
                            f"  [bold {_YL}]◈[/]  [bold {_FG}]PLAN SUMMARY[/]",
                            id="summary-header",
                        )

                        # 2×2 stat grid
                        with Horizontal(id="summary-grid-row1"):
                            with Vertical(classes="summary-stat-box"):
                                yield Static(f"[{_DIM}]STEPS[/]",      classes="summary-stat-label")
                                yield Static("—",                       classes="summary-stat-value", id="sum-steps")
                            with Vertical(classes="summary-stat-box"):
                                yield Static(f"[{_DIM}]TOOLS USED[/]", classes="summary-stat-label")
                                yield Static("—",                       classes="summary-stat-value", id="sum-tools")

                        with Horizontal(id="summary-grid-row2"):
                            with Vertical(classes="summary-stat-box"):
                                yield Static(f"[{_DIM}]RISK LEVEL[/]", classes="summary-stat-label")
                                yield Static("—",                       classes="summary-stat-value", id="sum-risk")
                            with Vertical(classes="summary-stat-box"):
                                yield Static(f"[{_DIM}]EST. TIME[/]",  classes="summary-stat-label")
                                yield Static("—",                       classes="summary-stat-value", id="sum-time")

                        # Metadata rows
                        with Vertical(id="summary-meta"):
                            yield Static(
                                f"[{_DIM}]Context Resolution[/]  [{_DIM}]—[/]",
                                id="sum-meta-ctx", classes="summary-meta-row"
                            )
                            yield Static(
                                f"[{_DIM}]Model Affinity[/]      [{_DIM}]—[/]",
                                id="sum-meta-model", classes="summary-meta-row"
                            )
                            yield Static(
                                f"[{_DIM}]Token Overhead[/]      [{_DIM}]—[/]",
                                id="sum-meta-tok", classes="summary-meta-row"
                            )

                # ── PIPELINE SECTION ──────────────────────────
                with Vertical(id="pipeline-section"):
                    with Horizontal(id="pipeline-header-row"):
                        yield Static(
                            f"[bold {_BL}]●[/] [bold {_DIM}]EXECUTION PIPELINE[/]",
                            id="pipeline-title",
                        )
                        yield Static(f"[{_DIM}]{'─' * 60}[/]", id="pipeline-divider")

                    with Horizontal(id="pipeline-cards-row"):
                        yield Static(
                            f"[{_DIM}]Generate a plan to see the execution pipeline.[/]",
                            id="pipeline-placeholder",
                        )

        from cli.components.footer import AppStatusBar
        yield AppStatusBar()

    # ── Lifecycle ────────────────────────────────────────────

    async def on_mount(self) -> None:
        self.query_one("#plan-builder-panel").border_title = " [bold #7AA2F7]Plan Builder[/] "
        self.query_one("#plan-builder-panel").border_subtitle = "[dim][Ctrl+G] Generate[/]"
        self.query_one("#plan-summary-panel").border_title = " [bold #E0AF68]◈ Plan Summary[/] "
        self.query_one("#pipeline-section").border_title = " [bold #7AA2F7]⚡ Execution Pipeline[/] "
        self.query_one("#plan-prompt", TextArea).focus()

        # Populate Model Affinity from policy
        try:
            policy = await api.get_policy()
            prov = policy.get("llm_provider", "gemini").upper()
            model_str = "Gemini Pro" if "gemini" in prov.lower() else "GPT-4o"
            self.query_one("#sum-meta-model", Static).update(
                f"[{_DIM}]Model Affinity  [/][{_FG}]{model_str} (Optimized)[/]"
            )
        except Exception:
            pass

    # ── Actions ──────────────────────────────────────────────

    def action_blur_or_pop(self) -> None:
        if isinstance(self.focused, (Input, Select, TextArea)):
            self.set_focus(None)
        else:
            self.app.pop_screen()

    def action_reset_form(self) -> None:
        prompt_widget = self.query_one("#plan-prompt", TextArea)
        prompt_widget.text = ""
        self.query_one("#plan-context", Input).clear()
        self.query_one("#plan-gen-status", Static).update("")
        self._reset_summary()
        self._clear_pipeline()

    def _reset_summary(self) -> None:
        for wid in ("sum-steps", "sum-tools", "sum-risk", "sum-time"):
            self.query_one(f"#{wid}", Static).update("—")
        self.query_one("#sum-meta-ctx", Static).update(
            f"[{_DIM}]Context Resolution   —[/]"
        )
        self.query_one("#sum-meta-tok", Static).update(
            f"[{_DIM}]Token Overhead       —[/]"
        )

    def _clear_pipeline(self) -> None:
        row = self.query_one("#pipeline-cards-row")
        for child in list(row.children):
            child.remove()
        row.mount(Static(
            f"[{_DIM}]Generate a plan to see the execution pipeline.[/]",
            id="pipeline-placeholder",
        ))

    @work(exclusive=True)
    async def action_generate_plan(self) -> None:
        if self._generating:
            return
        prompt  = self.query_one("#plan-prompt",  TextArea).text.strip()
        context = self.query_one("#plan-context", Input).value.strip() or None
        if not prompt:
            self.query_one("#plan-gen-status", Static).update(
                f"[bold {_RD}]✖ Prompt cannot be empty.[/]"
            )
            return

        session_id = getattr(self.app, "session_id", None)
        if not session_id or session_id == "OFFLINE":
            self.query_one("#plan-gen-status", Static).update(
                f"[bold {_RD}]✖ Session OFFLINE. Backend not reachable.[/]"
            )
            return

        self._generating = True
        self.query_one("#plan-gen-status", Static).update(
            f"[{_YL}]⏳ Generating plan… please wait[/]"
        )

        try:
            plan_resp = await api.create_plan(session_id, prompt, context)
            plan_id   = plan_resp["plan_id"]
            plan_data = await api.get_plan(session_id, plan_id)
            self._plan_data = plan_data
            self._populate_summary(plan_data, context)
            await self._populate_pipeline(plan_data)
            self.query_one("#plan-gen-status", Static).update(
                f"[bold {_GR}]✔ Plan generated!  [/][{_DIM}]Press [Ctrl+E] to execute.[/]"
            )
            # Store plan on app so Execute screen can pick it up
            self.app.current_plan_id = plan_id  # type: ignore[attr-defined]
        except Exception as exc:
            self.query_one("#plan-gen-status", Static).update(
                f"[bold {_RD}]✖ {exc}[/]"
            )
        finally:
            self._generating = False

    # ── Summary population ───────────────────────────────────

    def _populate_summary(self, plan: dict, context: str | None) -> None:
        steps      = plan.get("steps", [])
        tools      = list(dict.fromkeys(s.get("tool_name", "?") for s in steps))
        restricted = sum(1 for s in steps if not s.get("allowed", True))
        est_sec    = len(steps) * 2
        risk_color = _GR if not restricted else _RD
        risk_txt   = "LOW" if not restricted else f"{restricted} RISKY"

        self.query_one("#sum-steps", Static).update(f"[bold {_FG}]{len(steps):02d}[/]")
        self.query_one("#sum-tools", Static).update(f"[bold {_FG}]{len(tools):02d}[/]")
        self.query_one("#sum-risk",  Static).update(f"[bold {risk_color}]{risk_txt}[/]")
        self.query_one("#sum-time",  Static).update(
            f"[bold {_FG}]{est_sec}[/][{_DIM}] sec[/]"
        )
        ctx_txt = f"[{_GR}]SUCCESS[/]" if context else f"[{_DIM}]skipped[/]"
        self.query_one("#sum-meta-ctx", Static).update(
            f"[{_DIM}]Context Resolution[/]   {ctx_txt}"
        )
        tok_est = len(plan.get("goal", "")) // 4 + len(steps) * 120
        tok_str = f"~{tok_est // 100 / 10:.1f}k" if tok_est > 100 else str(tok_est)
        tok_color = _YL if tok_est > 800 else _FG
        self.query_one("#sum-meta-tok", Static).update(
            f"[{_DIM}]Token Overhead[/]   [{tok_color}]{tok_str}[/]"
        )

    # ── Pipeline population ──────────────────────────────────

    async def _populate_pipeline(self, plan: dict) -> None:
        steps = plan.get("steps", [])
        row   = self.query_one("#pipeline-cards-row")
        for child in list(row.children):
            child.remove()

        visible, rest = steps[:2], steps[2:]
        for i, step in enumerate(visible, 1):
            tool    = step.get("tool_name", "unknown")
            expl    = step.get("explanation", "")
            args    = step.get("arguments", {})
            allowed = step.get("allowed", True)
            badge   = _allowed_badge(allowed, tool)
            bc      = _badge_color(badge)
            policy  = "read_only" if "read" in tool else "scoped_sandbox"

            # Build first 2 lines of code snippet
            snippet_lines = []
            for k, v in list(args.items())[:2]:
                snippet_lines.append(
                    f"[{_DIM}]│[/] {tool}([{_FG}]{str(v)[:36]}[/])"
                )
            if len(args) > 2:
                snippet_lines.append(f"[{_DIM}]╰─ {len(args)-2} more args…[/]")
            snippet = "\n".join(snippet_lines) or f"[{_DIM}]│ (no arguments)[/]"

            card_text = (
                f"[bold {_BL}]STEP_{i:02d}[/]  {badge}\n"
                f"\n"
                f"[{_BL}]▶[/]  [bold {_FG}]{tool}[/]\n"
                f"\n"
                f"{snippet}\n"
                f"\n"
                f"[{_DIM}]POLICY: {policy.upper()}[/]  [{_DIM}]🔒[/]"
            )
            await row.mount(Static(card_text, classes="pipeline-step-card"))

        if rest:
            ghost = (
                f"[{_DIM}]      ···\n\n"
                f"STEPS {len(visible)+1}–{len(steps)} COLLAPSED[/]"
            )
            await row.mount(Static(ghost, classes="pipeline-step-card pipeline-ghost"))


# ══════════════════════════════════════════════════════════════
#  PLAN PREVIEW  (existing plan — read-only view)
# ══════════════════════════════════════════════════════════════

class PlanPreviewScreen(Screen):
    BINDINGS = [
        ("a",      "approve_plan", "Approve & Execute (Full)"),
        ("s",      "step_mode",    "Execute Step-by-Step"),
        ("escape", "app.pop_screen", "Back"),
    ]

    def __init__(self, plan_id: str, mode: str = "step", **kwargs):
        super().__init__(**kwargs)
        self.plan_id    = plan_id
        self.mode       = mode
        self._plan_data: dict = {}

    def compose(self) -> ComposeResult:
        yield TopMenu(active_tab="Plans")
        with Container(id="main-container"):
            with VerticalScroll(id="plans-scroll"):

                with Horizontal(id="plans-top-split"):
                    # Summary panel (left for preview)
                    with Vertical(id="plan-summary-panel"):
                        yield Static(f"[bold {_YL}]◈  PLAN SUMMARY[/]", id="summary-header")
                        with Horizontal(id="summary-grid-row1"):
                            with Vertical(classes="summary-stat-box"):
                                yield Static(f"[{_DIM}]STEPS[/]",      classes="summary-stat-label")
                                yield Static("…",                       classes="summary-stat-value", id="sum-steps")
                            with Vertical(classes="summary-stat-box"):
                                yield Static(f"[{_DIM}]TOOLS USED[/]", classes="summary-stat-label")
                                yield Static("…",                       classes="summary-stat-value", id="sum-tools")
                        with Horizontal(id="summary-grid-row2"):
                            with Vertical(classes="summary-stat-box"):
                                yield Static(f"[{_DIM}]RISK LEVEL[/]", classes="summary-stat-label")
                                yield Static("…",                       classes="summary-stat-value", id="sum-risk")
                            with Vertical(classes="summary-stat-box"):
                                yield Static(f"[{_DIM}]EST. TIME[/]",  classes="summary-stat-label")
                                yield Static("…",                       classes="summary-stat-value", id="sum-time")
                        with Vertical(id="summary-meta"):
                            yield Static("", id="sum-meta-ctx",   classes="summary-meta-row")
                            yield Static("", id="sum-meta-model", classes="summary-meta-row")
                            yield Static("", id="sum-meta-tok",   classes="summary-meta-row")

                    with Vertical(id="plan-actions-panel"):
                        yield Static(
                            f"[bold {_FG}]Plan ID:[/] [{_BL}]{self.plan_id[:16]}[/]",
                            id="preview-plan-id",
                        )
                        yield Static("", id="preview-goal", classes="plan-field-label")
                        yield Static(
                            f"\n[bold {_BL}][[A]][/] Approve & Execute (Full)\n"
                            f"[bold {_BL}][[S]][/] Execute Step-by-Step\n"
                            f"[bold {_DIM}][[Esc]][/] Back to Plans",
                            id="preview-keybinds",
                        )

                with Vertical(id="pipeline-section"):
                    with Horizontal(id="pipeline-header-row"):
                        yield Static(
                            f"[bold {_BL}]●[/] [bold {_DIM}]EXECUTION PIPELINE[/]",
                            id="pipeline-title",
                        )
                        yield Static(f"[{_DIM}]{'─' * 60}[/]", id="pipeline-divider")
                    with Horizontal(id="pipeline-cards-row"):
                        yield Static(f"[{_DIM}]Loading plan…[/]", id="pipeline-placeholder")

        from cli.components.footer import AppStatusBar
        yield AppStatusBar()

    async def on_mount(self) -> None:
        self.query_one("#plan-summary-panel").border_title = " [bold #E0AF68]◈ Plan Summary[/] "
        self.query_one("#pipeline-section").border_title   = " [bold #7AA2F7]⚡ Execution Pipeline[/] "
        self.fetch_plan()

    @work(exclusive=True)
    async def fetch_plan(self) -> None:
        session_id = getattr(self.app, "session_id", None)
        if not session_id or session_id == "OFFLINE":
            return
        try:
            plan = await api.get_plan(session_id, self.plan_id)
            self._plan_data = plan
            self._populate_summary(plan)
            await self._populate_pipeline(plan)
            self.query_one("#preview-goal", Static).update(
                f"[{_DIM}]{plan.get('goal', '')}[/]"
            )
        except Exception as exc:
            self.query_one("#pipeline-placeholder", Static).update(
                f"[bold {_RD}]✖ {exc}[/]"
            )

    def _populate_summary(self, plan: dict) -> None:
        steps      = plan.get("steps", [])
        tools      = list(dict.fromkeys(s.get("tool_name", "?") for s in steps))
        restricted = sum(1 for s in steps if not s.get("allowed", True))
        risk_color = _GR if not restricted else _RD
        risk_txt   = "LOW" if not restricted else f"{restricted} RISKY"
        self.query_one("#sum-steps", Static).update(f"[bold {_FG}]{len(steps):02d}[/]")
        self.query_one("#sum-tools", Static).update(f"[bold {_FG}]{len(tools):02d}[/]")
        self.query_one("#sum-risk",  Static).update(f"[bold {risk_color}]{risk_txt}[/]")
        self.query_one("#sum-time",  Static).update(
            f"[bold {_FG}]{len(steps) * 2}[/][{_DIM}] sec[/]"
        )
        self.query_one("#sum-meta-ctx", Static).update(
            f"[{_DIM}]Context Resolution[/]  [{_GR}]SUCCESS[/]"
        )
        self.query_one("#sum-meta-tok", Static).update(
            f"[{_DIM}]Token Overhead[/]      [{_YL}]~1.2k[/]"
        )

    async def _populate_pipeline(self, plan: dict) -> None:
        steps = plan.get("steps", [])
        row   = self.query_one("#pipeline-cards-row")
        for child in list(row.children):
            child.remove()
        visible, rest = steps[:2], steps[2:]
        for i, step in enumerate(visible, 1):
            tool    = step.get("tool_name", "unknown")
            allowed = step.get("allowed", True)
            badge   = _allowed_badge(allowed, tool)
            bc      = _badge_color(badge)
            args    = step.get("arguments", {})
            snippet_lines = []
            for k, v in list(args.items())[:2]:
                snippet_lines.append(
                    f"[{_DIM}]│[/] {tool}([{_FG}]{str(v)[:36]}[/])"
                )
            snippet = "\n".join(snippet_lines) or f"[{_DIM}]│ (no args)[/]"
            policy = "read_only" if "read" in tool else "scoped_sandbox"
            card_text = (
                f"[bold {_BL}]STEP_{i:02d}[/]  {badge}\n\n"
                f"[{_BL}]▶[/]  [bold {_FG}]{tool}[/]\n\n"
                f"{snippet}\n\n"
                f"[{_DIM}]POLICY: {policy.upper()}[/]  [{_DIM}]🔒[/]"
            )
            await row.mount(Static(card_text, classes="pipeline-step-card"))
        if rest:
            ghost = f"[{_DIM}]      ···\n\nSTEPS {len(visible)+1}–{len(steps)} COLLAPSED[/]"
            await row.mount(Static(ghost, classes="pipeline-step-card pipeline-ghost"))

    def action_approve_plan(self) -> None:
        from cli.screens.execute import ExecuteScreen
        self.app.pop_screen()
        self.app.push_screen(ExecuteScreen(plan_id=self.plan_id, mode="full"))

    def action_step_mode(self) -> None:
        from cli.screens.execute import ExecuteScreen
        self.app.pop_screen()
        self.app.push_screen(ExecuteScreen(plan_id=self.plan_id, mode="step"))
