from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

class AppStatusBar(Horizontal):
    """Bottom status bar — VS Code–style keyboard hints + file info."""

    def __init__(self, **kwargs):
        kwargs.setdefault("id", "app-footer")
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold #9ece6a]> _[/]"
            "   [#414868]│[/]   "
            "[bold #c0caf5]↑↓[/] [#565f89]Navigate[/]  "
            "[bold #c0caf5]Enter[/] [#565f89]Open[/]  "
            "[bold #c0caf5]/[/] [#565f89]Search[/]  "
            "[bold #c0caf5]?[/] [#565f89]Help[/]",
            id="footer-left",
        )
        yield Static(
            "[#565f89]UTF-8[/]   [bold #7aa2f7]python 3.11.2[/]"
            "   [#9ece6a]\ue0a0[/] [#c0caf5]main*[/]",
            id="footer-right",
        )

    def set_connected(self, connected: bool, host: str = "127.0.0.1:8000") -> None:
        """Connection state is shown in nav chips — footer keeps keyboard hints."""
        pass

