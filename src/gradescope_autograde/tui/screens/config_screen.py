from __future__ import annotations

from pathlib import Path

from textual import on, work
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
            Button("Show Questions from Rubric", id="show-questions", variant="default"),
            Label("Extra Grading Instructions (optional)", classes="field-label"),
            TextArea(
                text="",
                id="extra-instructions",
            ),
            Label("AI Model", classes="field-label"),
            ModelSelector(),
            Horizontal(
                Button("Fetch GS Questions", id="fetch-gs-questions", variant="default"),
                Button("Show Rubric Questions", id="show-questions", variant="default"),
            ),
            Label("Questions to Grade (comma-separated IDs, e.g. q1,q4)", classes="field-label"),
            Input(
                placeholder='Leave empty for all questions',
                id="question-ids",
            ),
            Horizontal(
                Button("Verbose", id="toggle-verbose", variant="default"),
                Button("Upload", id="toggle-upload", variant="default"),
                Button("Pages", id="toggle-pages", variant="default"),
                Button("Extract:Auto", id="toggle-extraction", variant="default"),
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

    def _toggle_btn(self, btn_id: str, attr: str, label_on: str, label_off: str) -> bool:
        val = not getattr(self, attr, False)
        setattr(self, attr, val)
        btn = self.query_one(f"#{btn_id}", Button)
        btn.variant = "primary" if val else "default"
        btn.label = label_on if val else label_off
        return val

    @on(Button.Pressed, "#fetch-gs-questions")
    def _fetch_gs_questions(self) -> None:
        status = self.query_one("#config-status", Static)
        try:
            from gradescope_autograde.client.client import GSClient
            from gradescope_autograde.transport.session import GSSession
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
            client = GSClient(session)
            gs_qs = client.list_questions(self.course_id, self.assignment_id)
            if gs_qs:
                lines = ["Questions from Gradescope:"]
                for q in gs_qs:
                    lines.append(f"  {q['id']}: {q['name']}")
                status.update("\n".join(lines))
            else:
                status.update("[yellow]No per-question columns in Gradescope for this assignment.[/]")
        except Exception as e:
            status.update(f"[error]Failed to fetch: {e}[/]")

    @on(Button.Pressed, "#show-questions")
    def _show_questions(self) -> None:
        rubric_path = self.query_one("#rubric-path", Input).value.strip()
        if not rubric_path:
            self.query_one("#config-status", Static).update("[warn]Enter a rubric path first[/]")
            return
        try:
            from gradescope_autograde.grader.rubric_parser import load_rubric, parse_questions

            rubric = load_rubric(rubric_path)
            questions = parse_questions(rubric)
            lines = ["Available questions:", f"{'ID':>6s}  {'Title':30s}  {'Points':>6s}"]
            for q in questions:
                lines.append(f"{q['id']:>6s}  {q['title']:30s}  {q['max_points']:>6.0f}")
            self.query_one("#config-status", Static).update("\n".join(lines))
        except Exception as e:
            self.query_one("#config-status", Static).update(f"[error]Error: {e}[/]")

    @on(Button.Pressed, "#toggle-verbose")
    def _toggle_verbose(self) -> None:
        self._toggle_btn("toggle-verbose", "_verbose", "Verbose*", "Verbose")

    @on(Button.Pressed, "#toggle-upload")
    def _toggle_upload(self) -> None:
        self._toggle_btn("toggle-upload", "_upload", "Upload*", "Upload")

    @on(Button.Pressed, "#toggle-pages")
    def _toggle_pages(self) -> None:
        self._toggle_btn("toggle-pages", "_with_pages", "Pages*", "Pages")

    @on(Button.Pressed, "#toggle-extraction")
    def _toggle_extraction(self) -> None:
        modes = ["auto", "ocr", "multimodal"]
        current = getattr(self, "_extraction", "auto")
        idx = (modes.index(current) + 1) % len(modes) if current in modes else 0
        self._extraction = modes[idx]
        labels = {"auto": "Extract:Auto", "ocr": "Extract:OCR", "multimodal": "Extract:MM"}
        btn = self.query_one("#toggle-extraction", Button)
        btn.label = labels[self._extraction]
        btn.variant = "primary" if self._extraction != "auto" else "default"

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
                extraction=getattr(self, "_extraction", "auto"),
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
