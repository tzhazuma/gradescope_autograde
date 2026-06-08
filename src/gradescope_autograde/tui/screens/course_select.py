from __future__ import annotations

from pathlib import Path

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, SelectionList, Static
from textual.widgets.selection_list import Selection

from gradescope_autograde.client.client import GSClient
from gradescope_autograde.transport.session import GSSession


class CourseSelectScreen(Screen):
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("escape", "go_back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Label("Select a Course", classes="screen-title"),
            Static("Connecting to Gradescope...", id="status"),
            SelectionList(id="course-list"),
            Horizontal(
                Button("Refresh", id="refresh", variant="default"),
                Button("Continue", id="continue", variant="primary", disabled=True),
                id="button-bar",
            ),
            id="main",
        )
        yield Footer()

    def on_mount(self) -> None:
        self._courses: list[dict] = []
        self._load_courses()

    @work(exclusive=True, thread=True)
    def _load_courses(self) -> None:
        try:
            session = self._create_session()
            client = GSClient(session)
            courses = client.list_courses()
            self.app.call_from_thread(self._populate_courses, courses)
        except FileNotFoundError:
            self.app.call_from_thread(
                self._show_error,
                "No config found. Run `gs-autograde login` first, then retry.",
            )
        except Exception as exc:
            self.app.call_from_thread(
                self._show_error,
                f"Failed to connect: {exc}",
            )

    def _create_session(self) -> GSSession:
        from gradescope_autograde.config import load_config

        cfg = load_config(self.app.config_path)
        session = GSSession(
            base_url=cfg.gradescope.base_url,
            request_delay=cfg.gradescope.request_delay,
            max_retries=cfg.gradescope.max_retries,
        )

        cookie_path = Path(".cookies/session.txt")
        if cookie_path.exists():
            session.load_cookies(cookie_path)
        elif cfg.auth.cookie:
            session.login_with_cookie(cfg.auth.cookie)
        elif cfg.auth.email and cfg.auth.password:
            if not session.login(cfg.auth.email, cfg.auth.password):
                raise RuntimeError("Login failed. Check credentials.")
        else:
            raise RuntimeError("No credentials found. Run `gs-autograde login` first.")

        return session

    def _populate_courses(self, courses: list[dict]) -> None:
        self._courses = courses
        status = self.query_one("#status", Static)
        selection_list = self.query_one("#course-list", SelectionList)

        if not courses:
            status.update("No courses found on your Gradescope account.")
            return

        status.update(f"Found {len(courses)} course(s). Select one and press Continue.")

        selections = [
            Selection(
                f"{c.get('name', 'Unknown')}  (ID: {c.get('id', '?')})",
                c.get("id", ""),
            )
            for c in courses
        ]
        selection_list.clear_options()
        selection_list.add_options(selections)

    def _show_error(self, message: str) -> None:
        status = self.query_one("#status", Static)
        status.update(f"[error]{message}[/]")

    @on(SelectionList.SelectedChanged)
    def _on_selection_changed(self) -> None:
        selection_list = self.query_one("#course-list", SelectionList)
        continue_btn = self.query_one("#continue", Button)
        continue_btn.disabled = len(selection_list.selected) == 0

    @on(Button.Pressed, "#continue")
    def _on_continue(self) -> None:
        selection_list = self.query_one("#course-list", SelectionList)
        selected = selection_list.selected
        if not selected:
            return

        course_id = selected[0]
        course_name = ""
        for c in self._courses:
            if c.get("id") == course_id:
                course_name = c.get("name", "")
                break

        from gradescope_autograde.tui.screens.assignment_select import (
            AssignmentSelectScreen,
        )

        self.app.push_screen(
            AssignmentSelectScreen(course_id=course_id, course_name=course_name)
        )

    @on(Button.Pressed, "#refresh")
    def _on_refresh(self) -> None:
        self.query_one("#status", Static).update("Refreshing courses...")
        self.query_one("#course-list", SelectionList).clear_options()
        self.query_one("#continue", Button).disabled = True
        self._load_courses()

    def action_go_back(self) -> None:
        self.app.action_quit()
