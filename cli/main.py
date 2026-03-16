from textual.app import App, ComposeResult
from textual.containers import Container
from textual.binding import Binding

from cli.screens.dashboard import DashboardScreen
from cli.screens.plans import PlanCreationScreen
from cli.screens.execute import ExecuteScreen
from cli.screens.files import FilesScreen
from cli.screens.tools import ToolsScreen
from cli.screens.policy import PolicyScreen
from cli.screens.history import HistoryScreen, LogsScreen
from cli.api_client import api

class MCPLinkApp(App):
    """The central Command Center Textual Application."""
    
    CSS_PATH = "styles.tcss"
    
    # Global state accessible to all screens
    session_id = None
    _offline_reason: str = ""
    
    BINDINGS = [
        Binding("q", "quit", "Quit", show=False),
        Binding("d", "switch_dashboard", "Dashboard", show=False),
        Binding("p", "switch_plans", "Plans", show=False),
        Binding("e", "switch_execute", "Execute", show=False),
        Binding("f", "switch_files", "Files", show=False),
        Binding("t", "switch_tools", "Tools", show=False),
        Binding("o", "switch_policy", "Policy", show=False),
        Binding("h", "switch_history", "History", show=False),
        Binding("l", "switch_logs", "Logs", show=False),
        Binding("ctrl+r", "reconnect", "Reconnect", show=False),
    ]
    
    async def on_mount(self) -> None:
        # Initialize a backend session right away
        try:
            self.session_id = await api.create_session()
        except Exception as e:
            self.session_id = "OFFLINE"
            self._offline_reason = str(e)
            
        self.push_screen(DashboardScreen(id="dashboard"))

    def action_switch_dashboard(self) -> None:
        self.pop_to_screen("dashboard")

    def action_switch_plans(self) -> None:
        self.push_screen(PlanCreationScreen())

    def action_switch_execute(self) -> None:
        self.push_screen(ExecuteScreen())

    def action_switch_files(self) -> None:
        self.push_screen(FilesScreen())

    def action_switch_tools(self) -> None:
        self.push_screen(ToolsScreen())

    def action_switch_policy(self) -> None:
        self.push_screen(PolicyScreen())

    def action_switch_history(self) -> None:
        self.push_screen(HistoryScreen())

    def action_switch_logs(self) -> None:
        self.push_screen(LogsScreen())

    async def action_reconnect(self) -> None:
        """Attempt to reconnect to the backend and refresh the session."""
        try:
            self.session_id = await api.create_session()
            self._offline_reason = ""
        except Exception as e:
            self.session_id = "OFFLINE"
            self._offline_reason = str(e)
        # Refresh whichever screen is on top
        if hasattr(self.screen, "update_status"):
            self.screen.update_status()

    def pop_to_screen(self, screen_id: str) -> None:
        """Helper to pop screens until we reach target without duplicating."""
        if self.screen.id != screen_id:
            while len(self.screen_stack) > 2: # Keep base App and Dashboard
                self.pop_screen()

if __name__ == "__main__":
    app = MCPLinkApp()
    app.run()
