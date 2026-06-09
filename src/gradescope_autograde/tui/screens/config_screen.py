from __future__ import annotations

from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
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
        yield VerticalScroll(
            Label("Grading Configuration", classes="screen-title"),
            Static(
                f"Course: {self.course_name}\n"
                f"Assignment: {self.assignment_title}  (ID: {self.assignment_id})"
            ),
            Label("Question PDF Path", classes="field-label"),
            Horizontal(
                Input(placeholder="data/input/question.pdf", id="question-pdf"),
                Button("Browse...", id="browse-pdf", variant="default"),
                classes="path-row",
            ),
            Label("Rubric File Path (.yaml/.yml/.pdf/.tex)", classes="field-label"),
            Horizontal(
                Input(placeholder="config/rubrics/default_rubric.yaml", id="rubric-path"),
                Button("Browse...", id="browse-rubric", variant="default"),
                classes="path-row",
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
            Horizontal(
                Button("Verbose", id="toggle-verbose", variant="default"),
                Static("OFF", id="verbose-status"),
                Button("Upload", id="toggle-upload", variant="default"),
                Static("OFF", id="upload-status"),
                Button("Pages", id="toggle-pages", variant="default"),
                Static("OFF", id="pages-status"),
                id="toggle-row",
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

    
    def _on_browse_file(self, input_id: str, file_types: list[str] | None = None) -> None:
        from gradescope_autograde.utils.file_picker import pick_file

        path = pick_file(
            title="Select a file",
            file_types=file_types,
        )
        if path:
            self.query_one(f"#{input_id}", Input).value = path

    @on(Button.Pressed, "#browse-pdf")
    def _browse_pdf(self) -> None:
        self._on_browse_file("question-pdf", ["pdf"])

    @on(Button.Pressed, "#browse-rubric")
    def _browse_rubric(self) -> None:
        self._on_browse_file("rubric-path", ["yaml", "yml", "pdf", "tex"])

    @on(Button.Pressed, "#toggle-verbose")
    def _toggle_verbose(self) -> None:
        self._verbose = not getattr(self, "_verbose", False)
        self.query_one("#toggle-verbose", Button).variant = "primary" if self._verbose else "default"
        self.query_one("#verbose-status", Static).update("   ON" if self._verbose else "   OFF")

    @on(Button.Pressed, "#toggle-upload")
    def _toggle_upload(self) -> None:
        self._upload = not getattr(self, "_upload", False)
        self.query_one("#toggle-upload", Button).variant = "primary" if self._upload else "default"
        self.query_one("#upload-status", Static).update("   ON" if self._upload else "   OFF")

    @on(Button.Pressed, "#toggle-pages")
    def _toggle_pages(self) -> None:
        self._with_pages = not getattr(self, "_with_pages", False)
        self.query_one("#toggle-pages", Button).variant = "primary" if self._with_pages else "default"
        self.query_one("#pages-status", Static).update("   ON" if self._with_pages else "   OFF")

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
                verbose=getattr(self, "_verbose", False),
                upload=getattr(self, "_upload", False),
                with_pages=getattr(self, "_with_pages", False),
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
