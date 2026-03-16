from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static
from textual.reactive import reactive

class StatusStrip(Horizontal):
    """Status strip showing session ID, mode, status, and policy underneath the header."""
    
    session_id = reactive("None")
    mode = reactive("IDLE")
    status = reactive("DISCONNECTED")
    
    def compose(self) -> ComposeResult:
        yield Static(id="status-left", classes="stat-box")
        yield Static(id="status-center", classes="stat-box")
        yield Static(id="status-right", classes="stat-box")

    def watch_session_id(self, old_val: str, new_val: str) -> None:
        self.update_display()
        
    def watch_mode(self, old_val: str, new_val: str) -> None:
        self.update_display()
        
    def watch_status(self, old_val: str, new_val: str) -> None:
        self.update_display()

    def update_display(self) -> None:
        left = self.query_one("#status-left", Static)
        center = self.query_one("#status-center", Static)
        right = self.query_one("#status-right", Static)
        
        display_id = self.session_id[:8] if self.session_id and self.session_id != "None" else "None"
        
        left.update(f"[dim]Session[/dim]   : [bold white]{display_id}[/bold white]")
        center.update(f"[dim]Mode[/dim]      : [bold white]{self.mode}[/bold white]")
        
        # Color coding status
        status_color = "white"
        if self.status in ["RUNNING", "EXECUTING"]:
            status_color = "yellow"
        elif self.status == "COMPLETED":
            status_color = "green"
        elif self.status == "FAILED":
            status_color = "red"
            
        right.update(f"[dim]Status[/dim]    : [bold {status_color}]{self.status}[/bold {status_color}]")
