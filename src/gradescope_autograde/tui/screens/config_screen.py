from __future__ import annotations

from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Static, TextArea

from gradescope_autograde.tui.widgets.model_selector import ModelSelector


class ConfigScreen(Screen):
    def __init__(
        self,
        course_id: str,
        course_name: str,
        assignment_id: str,
        assignment_title: str,
    ) -> None:
        super().__init__()
        self.course_id = course_id
        self.course_name = course_name
        self.assignment_id = assignment_id
        self.assignment_title = assignment_title

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("escape", "go_back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Label("Grading Configuration", classes="screen-title"),
            Static(
                f"Course: {self.course_name}\n"
                f"Assignment: {self.assignment_title}  (ID: {self.assignment_id})"
            ),
            Label("Question PDF Path", classes="field-label"),
            Input(
                placeholder="data/input/question.pdf",
                id="question-pdf",
            ),
            Label("Rubric File Path (.yaml/.yml/.pdf/.tex)", classes="field-label"),
            Input(
                placeholder="config/rubrics/default_rubric.yaml",
                id="rubric-path",
            ),
            Label("Extra Grading Instructions (optional)", classes="field-label"),
            TextArea(
                text="",
                id="extra-instructions",
            ),
            Label("AI Model", classes="field-label"),
            ModelSelector(),
            Label("Questions to Grade (comma-separated, e.g. q1,q3)", classes="field-label"),
            Input(
                placeholder="Leave empty to grade all questions",
                id="question-ids",
            ),
            Static("", id="config-status"),
            Horizontal(
                Button("Back", id="back", variant="default"),
                Button("Start Grading", id="start", variant="success"),
                id="button-bar",
            ),
            id="main",
        )
        yield Footer()

    @on(Button.Pressed, "#start")
    def _on_start(self) -> None:
        question_pdf = self.query_one("#question-pdf", Input).value.strip()
        rubric_path = self.query_one("#rubric-path", Input).value.strip()
        extra_instructions = self.query_one("#extra-instructions", TextArea).text.strip()
        model_selector = self.query_one("#model-select", ModelSelector)

        status = self.query_one("#config-status", Static)

        if not question_pdf:
            status.update("[error]Question PDF path is required.[/]")
            return

        if not rubric_path:
            rubric_path = "config/rubrics/default_rubric.yaml"

        model_info = model_selector.selected_model
        if model_info is None:
            status.update("[error]Please select an AI model.[/]")
            return

        provider_name, model_id = model_info

        rubric_data = self._load_rubric(rubric_path)
        if rubric_data is None:
            status.update(f"[error]Could not load rubric from: {rubric_path}[/]")
            return

        q_ids_raw = self.query_one("#question-ids", Input).value.strip()
        question_ids = [x.strip() for x in q_ids_raw.split(",") if x.strip()] if q_ids_raw else None

        from gradescope_autograde.tui.screens.grading_screen import GradingScreen

        self.app.push_screen(
            GradingScreen(
                course_id=self.course_id,
                assignment_id=self.assignment_id,
                question_pdf=question_pdf,
                rubric_path=rubric_path,
                rubric_data=rubric_data,
                extra_instructions=extra_instructions,
                provider_name=provider_name,
                model_id=model_id,
                question_ids=question_ids,
            )
        )

    def _load_rubric(self, path: str) -> dict | None:
        try:
            from gradescope_autograde.grader.rubric_parser import load_rubric as _load_rubric

            return _load_rubric(path)
        except Exception:
            return None

    @on(Button.Pressed, "#back")
    def _on_back(self) -> None:
        self.app.pop_screen()
