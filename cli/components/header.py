from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

_BLUE  = "#7AA2F7"
_DIM   = "#565F89"
_GREEN = "#9ECE6A"
_CYAN  = "#2AC3DE"

# Correct ANSI-shadow rows for MCPLINK V2 — "2" digit fixed
_LOGO_ROWS = [
    "  ███╗   ███╗ ██████╗██████╗ ██╗     ██╗███╗   ██╗██╗  ██╗  ██╗   ██╗██████╗      ",
    "  ████╗ ████║██╔════╝██╔══██╗██║     ██║████╗  ██║██║ ██╔╝  ██║   ██║╚════██╗     ",
    "  ██╔████╔██║██║     ██████╔╝██║     ██║██╔██╗ ██║█████╔╝   ██║   ██║ █████╔╝     ",
    "  ██║╚██╔╝██║██║     ██╔═══╝ ██║     ██║██║╚██╗██║██╔═██╗   ╚██╗ ██╔╝██╔═══╝      ",
    "  ██║ ╚═╝ ██║╚██████╗██║     ███████╗██║██║ ╚████║██║  ██╗   ╚████╔╝ ███████╗     ",
    "  ╚═╝     ╚═╝ ╚═════╝╚═╝     ╚══════╝╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝    ╚═══╝  ╚══════╝    ",
]

# Total box width = 90 chars (╔ + 88 inner + ╗)
_IW = 88          # inner width between │ and │
_MID = "─" * 74  # 74 dashes for bracket borders (7 + 74 + 7 = 88)

def _S(markup: str) -> Static:
    return Static(markup, classes="brand-logo-line")

class BrandHeader(Vertical):
    def compose(self) -> ComposeResult:
        # ── Top border  ╔──[ ◈ ]───...───[ ◈ ]──╗
        yield _S(f"[{_DIM}]╔──[ ◈ ]{_MID}[ ◈ ]──╗[/]")

        # ── Dot rail  │  [ ◈ ] ─·─·─·─ ... ─·─·─  [ ◈ ]  │
        dots = "─ · " * 18 + "─ "   # exactly 74 chars
        yield _S(f"[{_DIM}]│  [ ◈ ]{dots}[ ◈ ]  │[/]")

        # ── Blank row
        yield _S(f"[{_DIM}]│[/]{' ' * _IW}[{_DIM}]│[/]")

        # ── Logo rows (padded to _IW)
        for row in _LOGO_ROWS:
            padded = row.ljust(_IW)
            yield _S(f"[{_DIM}]│[/][bold {_BLUE}]{padded}[/][{_DIM}]│[/]")

        # ── Blank row
        yield _S(f"[{_DIM}]│[/]{' ' * _IW}[{_DIM}]│[/]")

        # ── MCPLink_V2 name rail — 88 chars inner
        # Layout: "  " + side(36) + " " = 39 | name(10) | " " + side(36) + "  " = 39  → 88 ✓
        side = "─ · " * 9      # 36 chars
        yield _S(
            f"[{_DIM}]│[/]"
            f"  [{_DIM}]{side}─[/]"
            f"[bold {_BLUE}]MCP[/][bold {_CYAN}]Link[/][{_DIM}]_[/][bold {_GREEN}]V2[/]"
            f"[{_DIM}]─{side}  [/]"
            f"[{_DIM}]│[/]"
        )

        # ── Mid divider  ├────...────┤
        yield _S(f"[{_DIM}]├{'─' * _IW}┤[/]")

        # ── Info bar — 88 chars inner
        # "  ⟨ AI Command Orchestration Platform ⟩" = 40
        # "          ● ACTIVE  ·  v2.0.4-stable  ·  Gemini  " = 48  →  total 88 ✓
        yield _S(
            f"[{_DIM}]│[/]"
            f"  [{_CYAN}]⟨[/] [{_DIM}]AI Command Orchestration Platform[/] [{_CYAN}]⟩[/]"
            f"          "
            f"[bold {_GREEN}]●[/] [{_GREEN}]ACTIVE[/]"
            f"  [{_DIM}]·[/]  [{_DIM}]v2.0.4-stable[/]"
            f"  [{_DIM}]·[/]  [{_DIM}]Gemini[/]"
            f"  [{_DIM}]│[/]"
        )

        # ── Bottom border  ╚──[ ◈ ]───...───[ ◈ ]──╝
        yield _S(f"[{_DIM}]╚──[ ◈ ]{_MID}[ ◈ ]──╝[/]")
