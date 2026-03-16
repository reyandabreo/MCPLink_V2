import datetime
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Static

# (hotkey, display-name)
_NAV_ENTRIES = [
    ("d", "DASHBOARD"),
    ("p", "PLANS"),
    ("e", "EXECUTE"),
    ("f", "FILES"),
    ("t", "TOOLS"),
    ("o", "POLICY"),
    ("h", "HISTORY"),
    ("l", "LOGS"),
]

class TopMenu(Container):
    """Two-row header: title+chips row / tab row.
    
    Chips are updated dynamically via update_chips().
    """

    DEFAULT_PROVIDER = "GEMINI"
    DEFAULT_WORKSPACE = "DEFAULT"

    def __init__(self, active_tab: str = "Dashboard", **kwargs):
        super().__init__(**kwargs)
        self.active_tab = active_tab
        self.id = "top-menu-container"

    def compose(self) -> ComposeResult:
        with Horizontal(id="header-row"):
            yield Static(
                " [bold #7AA2F7]\uf489  MCPLink v2 — AI Orchestration Console[/]",
                id="header-title",
            )
            with Horizontal(id="header-chips-container"):
                yield Static(
                    " [bold #9ECE6A]●[/] [bold #7AA2F7]SESSION: —[/] ",
                    classes="top-chip", id="chip-sess"
                )
                yield Static(
                    " [bold #565F89]WORKSPACE:[/] [bold #C0CAF5]DEFAULT[/] ",
                    classes="top-chip", id="chip-ws"
                )
                yield Static(
                    " [bold #565F89]PROVIDER:[/] [bold #7AA2F7]—[/] ",
                    classes="top-chip", id="chip-prov"
                )
                yield Static(
                    " [bold #7AA2F7]STATUS: —[/] ",
                    classes="top-chip chip-accent", id="chip-status"
                )

        with Horizontal(id="nav-row"):
            active_upper = self.active_tab.upper()
            yield Static("", id="nav-left-spacer")
            for _key, name in _NAV_ENTRIES:
                if name == active_upper:
                    yield Static(name, classes="nav-tab-active")
                else:
                    yield Static(name, classes="nav-tab")
            yield Static("", id="nav-spacer")

    def update_chips(
        self,
        session_id: str | None = None,
        provider: str = "—",
        connected: bool = False,
    ) -> None:
        """Refresh chip texts with live data from the backend."""
        try:
            sess_label = (session_id[:8] if session_id else "—").upper()
            sess_color = "#9ECE6A" if connected else "#F7768E"
            dot_color  = "#9ECE6A" if connected else "#F7768E"
            status_txt = "OK" if connected else "OFFLINE"
            status_col = "#9ECE6A" if connected else "#F7768E"
            prov_upper = provider.upper()

            self.query_one("#chip-sess", Static).update(
                f" [bold {dot_color}]●[/] [bold {sess_color}]SESSION: {sess_label}[/] "
            )
            self.query_one("#chip-prov", Static).update(
                f" [bold #565F89]PROVIDER:[/] [bold #7AA2F7]{prov_upper}[/] "
            )
            self.query_one("#chip-status", Static).update(
                f" [bold {status_col}]STATUS: {status_txt}[/] "
            )
        except Exception:
            pass


def get_shortcut_str() -> str:
    entries = [
        ("d", "Dash"), ("p", "Plans"), ("e", "Exec"),
        ("f", "Files"), ("t", "Tools"), ("o", "Policy"),
        ("h", "Hist"), ("l", "Logs"), ("ctrl+r", "Reconnect"), ("q", "Quit"),
    ]
    parts = [f"[bold #7AA2F7]{k}[/][#565F89]·{v}[/]" for k, v in entries]
    return "  ".join(parts)
