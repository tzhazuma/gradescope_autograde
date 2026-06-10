from __future__ import annotations

from pathlib import Path

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Static

from gradescope_autograde.tui.widgets.model_selector import ModelSelector


class RubricScreen(Screen):
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
            Label("Step 1: Rubric Setup", classes="screen-title"),
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
            Label("Rubric File Path (.yaml/.yml)", classes="field-label"),
            Horizontal(
                Input(placeholder="config/rubrics/default_rubric.yaml", id="rubric-path"),
                Button("Browse...", id="browse-rubric", variant="default"),
                classes="path-row",
            ),
            Button("Show Rubric Questions", id="show-questions", variant="default"),
            Label("--- Or Generate Rubric from PDF ---", classes="field-label"),
            Label("Answer PDF Path (optional)", classes="field-label"),
            Horizontal(
                Input(placeholder="data/input/answer.pdf", id="answer-pdf"),
                Button("Browse...", id="browse-answer", variant="default"),
                classes="path-row",
            ),
            Label("Rubric Generation Model", classes="field-label"),
            ModelSelector(id="rubric-model-select"),
            Button("Generate Rubric", id="generate-rubric", variant="success"),
            Static("", id="rubric-status"),
            id="main",
        )
        yield Footer()

    def _on_browse_file(self, input_id: str, file_types: list[str] | None = None) -> None:
        from gradescope_autograde.utils.file_picker import pick_file
        path = pick_file(title="Select a file", file_types=file_types)
        if path:
            self.app.call_from_thread(
                lambda: setattr(self.query_one(f"#{input_id}", Input), "value", path)
            )

    @on(Button.Pressed, "#browse-pdf")
    @work(thread=True)
    def _browse_pdf(self) -> None:
        self._on_browse_file("question-pdf", ["pdf"])

    @on(Button.Pressed, "#browse-rubric")
    @work(thread=True)
    def _browse_rubric(self) -> None:
        self._on_browse_file("rubric-path", ["yaml", "yml", "pdf", "tex"])

    @on(Button.Pressed, "#browse-answer")
    @work(thread=True)
    def _browse_answer(self) -> None:
        self._on_browse_file("answer-pdf", ["pdf"])

    @on(Button.Pressed, "#show-questions")
    def _show_questions(self) -> None:
        rubric_path = self.query_one("#rubric-path", Input).value.strip()
        if not rubric_path:
            self.query_one("#rubric-status", Static).update("[warn]Enter a rubric path first[/]")
            return
        try:
            from gradescope_autograde.grader.rubric_parser import load_rubric, parse_questions
            rubric = load_rubric(rubric_path)
            questions = parse_questions(rubric)
            lines = ["Available questions:", f"{'ID':>6s}  {'Title':30s}  {'Points':>6s}"]
            for q in questions:
                lines.append(f"{q['id']:>6s}  {q['title']:30s}  {q['max_points']:>6.0f}")
            self.query_one("#rubric-status", Static).update("\n".join(lines))
        except Exception as e:
            self.query_one("#rubric-status", Static).update(f"[error]Error: {e}[/]")

    @on(Button.Pressed, "#generate-rubric")
    @work(thread=True)
    def _generate_rubric(self) -> None:
        status = self.query_one("#rubric-status", Static)
        question_pdf = self.query_one("#question-pdf", Input).value.strip()
        if not question_pdf:
            status.update("[error]Question PDF path is required for rubric generation.[/]")
            return

        answer_pdf = self.query_one("#answer-pdf", Input).value.strip() or None
        model_selector = self.query_one("#rubric-model-select", ModelSelector)
        model_info = model_selector.selected_model

        if model_info is None:
            status.update("[error]Please select a model for rubric generation.[/]")
            return

        provider_name, model_id = model_info
        rubric_path = f"config/rubrics/generated_{self.assignment_id}.yaml"
        status.update(f"[dim]Generating rubric using {provider_name}/{model_id}...[/]\n[dim]Output: {rubric_path}[/]")
        try:
            from gradescope_autograde.grader.rubric_generator import generate_rubric
            from gradescope_autograde.config import load_config

            cfg = load_config(self.app.config_path)
            api_key = cfg.llm.api_key if hasattr(cfg.llm, 'api_key') else None

            rubric = generate_rubric(
                question_pdf=question_pdf,
                answer_pdf=answer_pdf,
                model=model_id,
                api_key=api_key,
                provider_type=provider_name,
            )

            Path(rubric_path).parent.mkdir(parents=True, exist_ok=True)
            import yaml
            with open(rubric_path, "w") as f:
                yaml.dump(rubric, f, default_flow_style=False)

            self.query_one("#rubric-path", Input).value = rubric_path
            status.update(f"[green]✓ Rubric generated with {len(rubric.get('questions', []))} questions[/]\n[green]✓ Saved to: {rubric_path}[/]")
        except Exception as e:
            status.update(f"[error]Rubric generation failed: {e}[/]")

    @on(Button.Pressed, "#next-step")
    def _go_to_grading(self) -> None:
        from gradescope_autograde.tui.screens.config_screen import ConfigScreen
        question_pdf = self.query_one("#question-pdf", Input).value.strip()
        rubric_path = self.query_one("#rubric-path", Input).value.strip()
        self.app.push_screen(ConfigScreen(
            course_id=self.course_id,
            course_name=self.course_name,
            assignment_id=self.assignment_id,
            assignment_title=self.assignment_title,
            question_pdf=question_pdf,
            rubric_path=rubric_path,
        ))

    def action_go_back(self) -> None:
        self.app.pop_screen()
