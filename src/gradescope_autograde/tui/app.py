from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.widgets import Footer, Header

from gradescope_autograde.config import load_config


class GradescopeTUI(App):
    TITLE = "Gradescope AutoGrade"
    CSS = """
    Screen {
        layout: vertical;
    }
    #main {
        width: 100%;
        height: 1fr;
        padding: 1 2;
        overflow-y: auto;
    }
    .screen-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    SelectionList {
        height: 1fr;
        margin-bottom: 1;
    }
    .error-message {
        color: $error;
        text-style: bold;
        margin: 1 0;
    }
    .info-message {
        color: $text-muted;
        margin: 1 0;
    }
    Button {
        margin: 0 1;
    }
    #button-bar {
        height: 3;
        align: center middle;
    }
    DataTable {
        height: 1fr;
    }
    RichLog {
        height: 1fr;
        border: solid $primary;
        margin: 1 0;
    }
    ProgressBar {
        margin: 1 0;
    }
    Input, TextArea {
        margin: 0 0 1 0;
    }
    .path-row {
        height: auto;
        margin-bottom: 1;
    }
    .path-row Input {
        width: 1fr;
    }
    .path-row Button {
        width: auto;
        min-width: 10;
    }
    .field-label {
        text-style: bold;
        color: $accent;
        margin-top: 1;
    }
    ToggleButton .toggle--label {
        text-style: dim;
        color: $text-muted;
    }
    ToggleButton.-on .toggle--label {
        text-style: bold;
        color: $text;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("escape", "go_back", "Back"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.config_path = "config/config.yaml"
        try:
            self.app_config = load_config(self.config_path)
        except FileNotFoundError:
            self.app_config = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(id="main")
        yield Footer()

    def on_mount(self) -> None:
        from gradescope_autograde.tui.screens.course_select import CourseSelectScreen

        self.push_screen(CourseSelectScreen())

    def action_go_back(self) -> None:
        if len(self.screen_stack) > 1:
            self.pop_screen()
