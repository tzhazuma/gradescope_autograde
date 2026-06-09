from __future__ import annotations

from pathlib import Path

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, ProgressBar, RichLog, Static

from gradescope_autograde.client.client import GSClient
from gradescope_autograde.grader.engine import GradingEngine
from gradescope_autograde.grader.providers.lmstudio import LMStudioProvider
from gradescope_autograde.grader.providers.opencode_go import OpenCodeGoProvider
from gradescope_autograde.grader.review import ReviewQueue
from gradescope_autograde.workflow.pipeline import Pipeline


class GradingScreen(Screen):
    def __init__(
        self,
        course_id: str,
        assignment_id: str,
        question_pdf: str,
        rubric_path: str,
        rubric_data: dict,
        extra_instructions: str,
        provider_name: str,
        model_id: str,
        question_ids: list[str] | None = None,
    ) -> None:
        super().__init__()
        self.course_id = course_id
        self.assignment_id = assignment_id
        self.question_pdf = question_pdf
        self.rubric_path = rubric_path
        self.rubric_data = rubric_data
        self.extra_instructions = extra_instructions
        self.provider_name = provider_name
        self.model_id = model_id
        self._question_ids = question_ids
        self._results: dict | None = None

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("escape", "go_back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Label("Grading in Progress", classes="screen-title"),
            Static(f"Assignment: {self.assignment_id}"),
            ProgressBar(total=100, id="progress"),
            RichLog(id="log", highlight=True, wrap=True),
            Horizontal(
                Button("View Results", id="results", variant="primary", disabled=True),
                id="button-bar",
            ),
            id="main",
        )
        yield Footer()

    def on_mount(self) -> None:
        self._run_grading()

    @work(exclusive=True, thread=True)
    def _run_grading(self) -> None:
        log = self.query_one("#log", RichLog)
        progress = self.query_one("#progress", ProgressBar)

        def log_msg(msg: str) -> None:
            self.app.call_from_thread(log.write, msg)

        def update_progress(completed: int, total: int) -> None:
            if total > 0:
                pct = int((completed / total) * 100)
                self.app.call_from_thread(progress.update, progress=pct)

        try:
            log_msg("Initializing session...")
            session = self._create_session()
            client = GSClient(session)

            log_msg(f"Creating grading engine with {self.provider_name}::{self.model_id}...")
            provider = self._create_provider()
            engine = GradingEngine(provider=provider)
            review_queue = ReviewQueue(
                threshold=self.app.app_config.workflow.review_threshold
                if self.app.app_config
                else 0.7
            )

            pipeline = Pipeline(
                client=client,
                engine=engine,
                review_queue=review_queue,
            )

            log_msg("Fetching submissions...")
            submissions = client.list_submissions(self.course_id, self.assignment_id)
            total = len(submissions)
            log_msg(f"Found {total} submission(s). Starting grading...")
            progress.update(total=total)

            results_list: list[dict] = []
            for i, sub in enumerate(submissions):
                sub_id = sub.get("id", str(i))
                student = sub.get("student_name", f"Student {i}")
                log_msg(f"[{i + 1}/{total}] Grading {student} (ID: {sub_id})...")

                try:
                    content = client.get_submission_content(
                        self.course_id, self.assignment_id, sub_id
                    )
                    answer_text = self._extract_answer(content)

                    all_qs = self.rubric_data.get("questions", [])
                    questions = (
                        [q for q in all_qs if q.get("id") in self._question_ids]
                        if self._question_ids else all_qs
                    )
                    for question in questions:
                        result = engine.grade(
                            question=question,
                            student_answer=answer_text,
                            extra_instructions=self.extra_instructions,
                        )
                        result["submission_id"] = sub_id
                        result["student_name"] = student
                        review_queue.check(sub_id, result)
                        results_list.append(result)

                        score = result.get("score", 0)
                        max_pts = question.get("max_points", "?")
                        confidence = result.get("confidence", 0)
                        log_msg(
                            f"  → {question.get('title', 'Q')}: "
                            f"{score}/{max_pts} (confidence: {confidence:.0%})"
                        )

                    update_progress(i + 1, total)

                except Exception as exc:
                    log_msg(f"  [error]Error grading {student}: {exc}[/]")
                    results_list.append({
                        "submission_id": sub_id,
                        "student_name": student,
                        "question_id": "error",
                        "score": 0,
                        "confidence": 0,
                        "feedback": f"Error: {exc}",
                        "flags": ["needs_review"],
                    })
                    update_progress(i + 1, total)

            self._results = {
                "summary": {
                    "completed": total,
                    "failed": sum(1 for r in results_list if "error" in r.get("flags", [])),
                    "total": total,
                },
                "review_count": review_queue.count,
                "results": results_list,
            }

            log_msg("")
            log_msg("=" * 50)
            log_msg(f"Grading complete! {total} submissions processed.")
            log_msg(f"Review queue: {review_queue.count} item(s) need attention.")
            log_msg("Press 'View Results' to see the full results.")

            self.app.call_from_thread(
                lambda: setattr(
                    self.query_one("#results", Button), "disabled", False
                )
            )

        except Exception as exc:
            log_msg(f"[error]Pipeline failed: {exc}[/]")

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
                raise RuntimeError("Login failed.")
        else:
            raise RuntimeError("No credentials found.")

        return session

    def _create_provider(self):
        if self.provider_name == "lmstudio":
            provider = LMStudioProvider(model=self.model_id)
        else:
            from gradescope_autograde.config import load_config

            cfg = load_config(self.app.config_path)
            provider = OpenCodeGoProvider(
                model=self.model_id,
                api_key=cfg.llm.api_key or None,
            )
        return provider

    def _extract_answer(self, content: bytes) -> str:
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                import pymupdf

                doc = pymupdf.open(stream=content, filetype="pdf")
                text = "\n".join(page.get_text() for page in doc)
                doc.close()
                return text
            except Exception:
                return "[Could not extract text from submission]"

    @on(Button.Pressed, "#results")
    def _on_results(self) -> None:
        if self._results:
            from gradescope_autograde.tui.screens.results_screen import ResultsScreen

            self.app.push_screen(ResultsScreen(results=self._results))
