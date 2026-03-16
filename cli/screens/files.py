import os
import datetime
from pathlib import Path
from rich.console import Group
from rich.style import Style as RichStyle
from rich.syntax import Syntax
from rich.text import Text
from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Container, Vertical, Horizontal, ScrollableContainer, VerticalScroll
from textual.widgets import Static, DirectoryTree, Button
from textual.widgets._directory_tree import TOGGLE_STYLE

from cli.components.nav import TopMenu, get_shortcut_str

# Always resolve sandbox relative to this file's project root
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
SANDBOX_PATH = str(_PROJECT_ROOT / "app" / "sandbox" / "workspace")

# Extension → (icon, hex_color, type_label)
# Nerd Font icons matching nvim-web-devicons / LazyVim style.
_EXT_ICONS: dict[str, tuple[str, str, str]] = {
    ".py":    ("\ue235", "#3572A5", "Python"),       # nf-dev-python
    ".js":    ("\ue74e", "#f7df1e", "JavaScript"),   # nf-dev-javascript
    ".ts":    ("\ue628", "#3178c6", "TypeScript"),   # nf-dev-typescript
    ".json":  ("\ue60b", "#cbcb41", "JSON"),         # nf-custom-json
    ".yaml":  ("\ue615", "#d29922", "YAML"),         # nf-custom-yaml
    ".yml":   ("\ue615", "#d29922", "YAML"),
    ".toml":  ("\ue615", "#9c4121", "TOML"),         # nf-custom-toml
    ".txt":   ("\uf15b", "#c0caf5", "Text"),         # nf-fa-file
    ".md":    ("\ue609", "#519aba", "Markdown"),     # nf-custom-markdown
    ".sh":    ("\uf489", "#4EAA25", "Shell Script"), # nf-oct-terminal
    ".bash":  ("\uf489", "#4EAA25", "Bash Script"),
    ".log":   ("\uf831", "#bc8cff", "Log File"),     # nf-mdi-file_document
    ".env":   ("\uf462", "#f85149", "Env Config"),   # nf-fa-lock
    ".csv":   ("\uf1c3", "#89d185", "CSV Data"),     # nf-fa-file_excel_o
    ".html":  ("\ue736", "#e34c26", "HTML"),         # nf-dev-html5
    ".css":   ("\ue749", "#563d7c", "CSS"),          # nf-dev-css3
    ".sql":   ("\ue706", "#e38c00", "SQL"),          # nf-dev-mysql
    ".xml":   ("\ue60b", "#d29922", "XML"),
    ".png":   ("\uf1c5", "#a074c4", "Image"),        # nf-fa-file_image_o
    ".jpg":   ("\uf1c5", "#a074c4", "Image"),
    ".jpeg":  ("\uf1c5", "#a074c4", "Image"),
    ".gif":   ("\uf1c5", "#a074c4", "Image"),
    ".svg":   ("\uf1c5", "#ffb13b", "SVG"),
    ".zip":   ("\uf1c6", "#7d8590", "Archive"),      # nf-fa-file_archive_o
    ".tar":   ("\uf1c6", "#7d8590", "Archive"),
    ".gz":    ("\uf1c6", "#7d8590", "Archive"),
    ".pdf":   ("\uf1c1", "#f85149", "PDF"),          # nf-fa-file_pdf_o
    ".rs":    ("\ue7a8", "#ce412b", "Rust"),         # nf-dev-rust
    ".go":    ("\ue627", "#00ACD7", "Go"),           # nf-dev-go
    ".c":     ("\ue61e", "#555555", "C"),            # nf-custom-c
    ".cpp":   ("\ue61d", "#f34b7d", "C++"),          # nf-custom-cpp
    ".java":  ("\ue256", "#b07219", "Java"),         # nf-dev-java
    ".rb":    ("\ue791", "#CC342D", "Ruby"),         # nf-dev-ruby
    ".php":   ("\ue73d", "#4F5D95", "PHP"),          # nf-dev-php
    ".kt":    ("\ue634", "#A97BFF", "Kotlin"),       # nf-dev-kotlin
    ".swift": ("\ue755", "#F05138", "Swift"),        # nf-dev-swift
    ".lua":   ("\ue620", "#000080", "Lua"),          # nf-dev-lua
    ".r":     ("\ue235", "#198CE7", "R Script"),
    ".ipynb": ("\ue745", "#DA5B0B", "Notebook"),     # nf-dev-python (notebook)
    ".proto": ("\ue60b", "#00bcd4", "Protobuf"),
    ".lock":  ("\uf83d", "#7d8590", "Lock File"),    # nf-mdi-lock
    ".cfg":   ("\ue615", "#d29922", "Config"),
    ".ini":   ("\ue615", "#d29922", "Config"),
    ".conf":  ("\ue615", "#d29922", "Config"),
    ".pem":   ("\uf462", "#f85149", "Certificate"),  # nf-fa-lock
    ".key":   ("\uf462", "#f85149", "Key File"),
}
_DEFAULT_ICON  = ("\uf15b", "#7d8590", "File")   # nf-fa-file
_FOLDER_ICON   = "\ue5ff"                          # nf-custom-folder (closed)
_FOLDER_OPEN   = "\ue5fe"                          # nf-custom-folder_open
_FOLDER_COLOR  = "#f7c948"                         # warm amber matching LazyVim


class IconDirectoryTree(DirectoryTree):
    """DirectoryTree subclass with Nerd Font icons per file extension."""

    def render_label(self, node, base_style, style) -> Text:
        node_label = node._label.copy()
        node_label.stylize(style)

        if not self.is_mounted:
            return node_label

        if node._allow_expand:
            # Directory node
            icon = _FOLDER_OPEN if node.is_expanded else _FOLDER_ICON
            icon_style = base_style + TOGGLE_STYLE + RichStyle(color=_FOLDER_COLOR)
            prefix = (f"{icon} ", icon_style)
            node_label.stylize_before(
                self.get_component_rich_style("directory-tree--folder", partial=True)
            )
        else:
            # File node — pick icon by extension
            try:
                path = node.data.path
                ext  = path.suffix.lower()
            except Exception:
                ext  = ""
            icon_char, color, _ = _EXT_ICONS.get(ext, _DEFAULT_ICON)
            prefix = (f"{icon_char} ", base_style + RichStyle(color=color))
            node_label.stylize_before(
                self.get_component_rich_style("directory-tree--file", partial=True)
            )
            node_label.highlight_regex(
                r"\..+$",
                self.get_component_rich_style(
                    "directory-tree--extension", partial=True
                ),
            )

        if node_label.plain.startswith("."):
            node_label.stylize_before(
                self.get_component_rich_style("directory-tree--hidden", partial=True)
            )

        return Text.assemble(prefix, node_label)


class FilesScreen(Screen):
    """Sandbox file manager — 3-column explorer / viewer / metadata layout."""

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("d", "action_delete_file", "Delete"),
        ("r", "action_reload_tree", "Reload"),
    ]

    _LANG_MAP: dict[str, str] = {
        ".py":   "python",      ".js":   "javascript", ".ts":  "typescript",
        ".json": "json",        ".yaml": "yaml",       ".yml": "yaml",
        ".toml": "toml",        ".md":   "markdown",   ".sh":  "bash",
        ".bash": "bash",        ".html": "html",       ".css": "css",
        ".sql":  "sql",         ".xml":  "xml",        ".rs":  "rust",
        ".go":   "go",          ".c":    "c",          ".cpp": "cpp",
        ".java": "java",        ".rb":   "ruby",       ".php": "php",
        ".lua":  "lua",
    }

    _BINARY_EXTS = frozenset({
        ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico",
        ".zip", ".tar", ".gz",  ".pdf", ".exe", ".bin", ".so", ".dll",
    })

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._selected_path: str = ""
        self._selected_is_dir: bool = False
        os.makedirs(SANDBOX_PATH, exist_ok=True)

    def compose(self) -> ComposeResult:
        yield TopMenu(active_tab="Files")

        # ── Workspace hero banner ──────────────────────────────────────────
        with Horizontal(id="workspace-hero"):
            yield Static(
                "  [bold #2ac3de]ACTIVE WORKSPACE[/]",
                id="hero-label",
            )
            yield Static(
                f"  [bold #c0caf5]{SANDBOX_PATH}[/]",
                id="hero-path",
            )

        with Container(id="main-container"):
            with Horizontal(id="files-split"):

                # ── LEFT: Explorer sidebar ─────────────────────────────────
                with Vertical(id="files-explorer"):
                    with Horizontal(id="explorer-header-row"):
                        yield Static(
                            " [bold #565f89]EXPLORER[/]",
                            id="explorer-label",
                        )
                        yield Static("[dim]＋[/]", id="explorer-new-btn")
                    yield IconDirectoryTree(SANDBOX_PATH, id="sandbox-tree")

                # ── CENTER: Code viewer ────────────────────────────────────
                with Vertical(id="files-viewer"):
                    with Horizontal(id="viewer-titlebar"):
                        yield Static("●", id="dot-red", classes="dot-red")
                        yield Static("●", id="dot-yel", classes="dot-yel")
                        yield Static("●", id="dot-grn", classes="dot-grn")
                        yield Static(" │ ", id="viewer-dot-sep")
                        yield Static("No file selected", id="viewer-tab-label")
                        yield Static("[dim]⎘[/]",  id="viewer-copy-btn")
                        yield Static("[dim]⛶[/]",  id="viewer-expand-btn")
                    with ScrollableContainer(id="viewer-body"):
                        yield Static(
                            "\n  [#565F89]Select a file from the explorer "
                            "to view its contents.[/]",
                            id="viewer-code",
                        )

                # ── RIGHT: Info panel ──────────────────────────────────────
                with VerticalScroll(id="files-info-panel"):

                    # ── Metadata ───────────────────────────────────────────
                    yield Static(
                        " [bold #565f89]METADATA[/]",
                        classes="info-section-label",
                    )
                    with Horizontal(classes="info-meta-row"):
                        yield Static("[#565f89]Type[/]",     classes="info-meta-key")
                        yield Static("—", id="info-type-val", classes="info-meta-val info-val-cyan")
                    with Horizontal(classes="info-meta-row"):
                        yield Static("[#565f89]Size[/]",     classes="info-meta-key")
                        yield Static("—", id="info-size-val", classes="info-meta-val")
                    with Horizontal(classes="info-meta-row"):
                        yield Static("[#565f89]Modified[/]", classes="info-meta-key")
                        yield Static("—", id="info-mod-val",  classes="info-meta-val")
                    yield Static(
                        "[#565f89]Full Path[/]",
                        classes="info-fullpath-label",
                    )
                    yield Static("—", id="info-path-box", classes="info-path-box")
                    yield Static("[#24283b]" + "─" * 32, classes="info-separator")

                    # ── Actions ────────────────────────────────────────────
                    yield Static(
                        " [bold #565f89]ACTIONS[/]",
                        classes="info-section-label",
                    )
                    yield Button("▶  Open",    id="info-btn-open",   classes="info-btn-open")
                    with Horizontal(id="info-btn-sec-row"):
                        yield Button("✎  Rename", id="info-btn-rename", classes="info-btn-sec")
                        yield Button("  Delete",  id="info-btn-del",    classes="info-btn-del")
                    yield Static("[#24283b]" + "─" * 32, classes="info-separator")

                    # ── Open With ─────────────────────────────────────────
                    yield Static(
                        " [bold #565f89]OPEN WITH[/]",
                        classes="info-section-label",
                    )
                    with Horizontal(id="info-open-with-item"):
                        with Vertical(id="info-ow-icon-bg"):
                            yield Static("[bold #bb9af7]⬡[/]", id="info-ow-icon")
                        with Vertical(id="info-ow-details"):
                            yield Static(
                                "[bold #c0caf5]python_executor[/]",
                                id="info-ow-name",
                            )
                            yield Static(
                                "[#565f89]System Tool[/]",
                                id="info-ow-sub",
                            )
                        yield Static("[dim]⚡[/]", id="info-ow-bolt")

    async def on_mount(self) -> None:
        session_id = getattr(self.app, "session_id", None)
        try:
            chip = self.query_one("#chip-sess", Static)
            if session_id and session_id != "OFFLINE":
                chip.update(
                    f" [bold #9ECE6A]●[/] [#9ECE6A]SESSION:[/]"
                    f" [bold #C0CAF5]{session_id[:8].upper()}[/] "
                )
            else:
                chip.update(
                    " [bold #F7768E]●[/] [#F7768E]SESSION: OFFLINE[/] "
                )
        except Exception:
            pass

    # ── Info panel helpers ─────────────────────────────────────────────────

    def _update_info_meta(
        self,
        ftype: str,
        size_str: str,
        mod_str: str,
        path_str: str,
    ) -> None:
        try:
            self.query_one("#info-type-val", Static).update(f"[#2ac3de]{ftype}[/]")
            self.query_one("#info-size-val", Static).update(f"[#c0caf5]{size_str}[/]")
            self.query_one("#info-mod-val",  Static).update(f"[#c0caf5]{mod_str}[/]")
            # Display full path with proper truncation for readability
            display_path = (
                path_str if len(path_str) <= 32 else "…" + path_str[-31:]
            )
            self.query_one("#info-path-box", Static).update(
                f"[#c0caf5]{display_path}[/]"
            )
        except Exception:
            pass

    def _clear_info_meta(self) -> None:
        for wid in ("#info-type-val", "#info-size-val", "#info-mod-val", "#info-path-box"):
            try:
                self.query_one(wid, Static).update("—")
            except Exception:
                pass

    # ── Event handlers ─────────────────────────────────────────────────────

    def on_tree_node_highlighted(self, event: DirectoryTree.NodeHighlighted) -> None:
        try:
            path = event.node.data.path
        except Exception:
            return
        path_str = str(path)
        self._selected_path   = path_str
        self._selected_is_dir = path.is_dir()

        if self._selected_is_dir:
            self._update_info_meta("Directory", "—", "—", path_str)
            try:
                self.query_one("#viewer-tab-label", Static).update(
                    f"[#bb9af7]{_FOLDER_ICON}  {path.name}/[/]"
                )
            except Exception:
                pass
        else:
            ext               = path.suffix.lower()
            icon, color, ftype = _EXT_ICONS.get(ext, _DEFAULT_ICON)
            size_str          = self._get_size_str(path_str)
            try:
                mtime   = os.path.getmtime(path_str)
                mod_str = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            except Exception:
                mod_str = "?"
            self._update_info_meta(ftype, size_str, mod_str, path_str)
            try:
                self.query_one("#viewer-tab-label", Static).update(
                    f"[{color}]{icon}  {path.name}[/]"
                    f" [#565f89]— {size_str}[/]"
                )
            except Exception:
                pass

    def on_directory_tree_file_selected(
        self, event: DirectoryTree.FileSelected
    ) -> None:
        self._selected_path   = str(event.path)
        self._selected_is_dir = False
        self._load_file_content(self._selected_path)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "info-btn-open":
            if self._selected_path and not self._selected_is_dir:
                self._load_file_content(self._selected_path)
        elif btn_id == "info-btn-del":
            self.action_delete_file()
        # Rename — placeholder for future dialog

    # ── File operations ────────────────────────────────────────────────────

    def _get_size_str(self, path: str) -> str:
        try:
            b = os.path.getsize(path)
            if b >= 1024 * 1024:
                return f"{b / 1024 / 1024:.1f} MB"
            elif b >= 1024:
                return f"{b / 1024:.1f} KB"
            return f"{b} B"
        except Exception:
            return "?"

    def _load_file_content(self, path: str) -> None:
        ext               = Path(path).suffix.lower()
        icon, color, ftype = _EXT_ICONS.get(ext, _DEFAULT_ICON)
        filename          = os.path.basename(path)
        size_str          = self._get_size_str(path)

        viewer    = self.query_one("#viewer-code",      Static)
        tab_label = self.query_one("#viewer-tab-label", Static)
        tab_label.update(
            f"[{color}]{icon}  {filename}[/] [#565f89]— {size_str}[/]"
        )
        viewer.update("[#565f89]Loading…[/]")

        if ext in self._BINARY_EXTS:
            viewer.update("[#565f89]Binary file — cannot display contents.[/]")
            return

        try:
            size_bytes = os.path.getsize(path)
            MAX_BYTES  = 8000
            with open(path, "r", errors="replace") as fh:
                raw = fh.read(MAX_BYTES)

            lang   = self._LANG_MAP.get(ext, "text")
            syntax = Syntax(
                raw,
                lang,
                theme="monokai",
                line_numbers=True,
                word_wrap=False,
            )

            if size_bytes > MAX_BYTES:
                truncation = Text(
                    f"\n⋯  Showing first {MAX_BYTES // 1024} KB of {size_str}",
                    style="#565F89",
                )
                viewer.update(Group(syntax, truncation))
            else:
                viewer.update(syntax)

        except Exception as e:
            viewer.update(f"[#f85149]✖  Cannot read file:[/] [white]{e}[/]")

    def action_delete_file(self) -> None:
        if not self._selected_path or self._selected_is_dir:
            try:
                self.query_one("#info-type-val", Static).update(
                    "[#d29922]Select a file to delete[/]"
                )
            except Exception:
                pass
            return
        name = os.path.basename(self._selected_path)
        try:
            os.remove(self._selected_path)
            self._clear_info_meta()
            try:
                self.query_one("#viewer-tab-label", Static).update("No file selected")
                self.query_one("#viewer-code", Static).update(
                    f"\n  [#9ECE6A]✔  Deleted:[/] [white]{name}[/]"
                )
            except Exception:
                pass
            self._selected_path = ""
            self.action_reload_tree()
        except Exception as e:
            try:
                self.query_one("#info-type-val", Static).update(
                    f"[#f85149]Delete failed: {e}[/]"
                )
            except Exception:
                pass

    def action_reload_tree(self) -> None:
        tree = self.query_one("#sandbox-tree", IconDirectoryTree)
        tree.reload()

