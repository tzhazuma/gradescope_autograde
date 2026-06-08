from __future__ import annotations

from pathlib import Path

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, SelectionList, Static
from textual.widgets.selection_list import Selection

from gradescope_autograde.client.client import GSClient


class AssignmentSelectScreen(Screen):
    def __init__(self, course_id: str, course_name: str) -> None:
        super().__init__()
        self.course_id = course_id
        self.course_name = course_name

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("escape", "go_back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Label(
                f"Assignments for: {self.course_name}",
                classes="screen-title",
            ),
            Static("Loading assignments...", id="status"),
            SelectionList(id="assignment-list"),
            Horizontal(
                Button("Back", id="back", variant="default"),
                Button("Continue", id="continue", variant="primary", disabled=True),
                id="button-bar",
            ),
            id="main",
        )
        yield Footer()

    def on_mount(self) -> None:
        self._assignments: list[dict] = []
        self._load_assignments()

    @work(exclusive=True, thread=True)
    def _load_assignments(self) -> None:
        try:
            session = self._create_session()
            client = GSClient(session)
            assignments = client.list_assignments(self.course_id)
            self.app.call_from_thread(self._populate_assignments, assignments)
        except Exception as exc:
            self.app.call_from_thread(
                self._show_error, f"Failed to load assignments: {exc}"
            )

    def _populate_assignments(self, assignments: list[dict]) -> None:
        self._assignments = assignments
        status = self.query_one("#status", Static)
        selection_list = self.query_one("#assignment-list", SelectionList)

        if not assignments:
            status.update("No assignments found for this course.")
            return

        status.update(
            f"Found {len(assignments)} assignment(s). Select one and press Continue."
        )

        selections = []
        for a in assignments:
            title = a.get("title", "Untitled")
            due = a.get("due_date", "No due date")
            submissions = a.get("submission_count", "?")
            label = f"{title}  |  Due: {due}  |  Submissions: {submissions}"
            selections.append(Selection(label, a.get("id", "")))

        selection_list.clear_options()
        selection_list.add_options(selections)

    def _show_error(self, message: str) -> None:
        self.query_one("#status", Static).update(f"[error]{message}[/]")

    @on(SelectionList.SelectedChanged)
    def _on_selection_changed(self) -> None:
        selection_list = self.query_one("#assignment-list", SelectionList)
        continue_btn = self.query_one("#continue", Button)
        continue_btn.disabled = len(selection_list.selected) == 0

    @on(Button.Pressed, "#continue")
    def _on_continue(self) -> None:
        selection_list = self.query_one("#assignment-list", SelectionList)
        selected = selection_list.selected
        if not selected:
            return

        assignment_id = selected[0]
        assignment_title = ""
        for a in self._assignments:
            if a.get("id") == assignment_id:
                assignment_title = a.get("title", "")
                break

        from gradescope_autograde.tui.screens.config_screen import ConfigScreen

        self.app.push_screen(
            ConfigScreen(
                course_id=self.course_id,
                course_name=self.course_name,
                assignment_id=assignment_id,
                assignment_title=assignment_title,
            )
        )

    def _create_session(self):
        from gradescope_autograde.config import load_config
        from gradescope_autograde.transport.session import GSSession

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

    @on(Button.Pressed, "#back")
    def _on_back(self) -> None:
        self.app.pop_screen()
