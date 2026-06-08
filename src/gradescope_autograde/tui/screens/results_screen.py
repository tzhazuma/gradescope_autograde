from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Label, Static

from gradescope_autograde.workflow.export import export_grades_csv


class ResultsScreen(Screen):
    def __init__(self, results: dict) -> None:
        super().__init__()
        self.results = results

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("escape", "go_back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Label("Grading Results", classes="screen-title"),
            Static(self._build_summary(), id="summary"),
            DataTable(id="results-table"),
            Vertical(
                Button("Export CSV", id="export-csv", variant="default"),
                Button("Export JSON", id="export-json", variant="default"),
                Button("Done", id="done", variant="primary"),
                id="button-bar",
            ),
            id="main",
        )
        yield Footer()

    def on_mount(self) -> None:
        self._populate_table()

    def _build_summary(self) -> str:
        summary = self.results.get("summary", {})
        review_count = self.results.get("review_count", 0)
        completed = summary.get("completed", 0)
        failed = summary.get("failed", 0)
        total = summary.get("total", 0)

        lines = [
            f"Total submissions: {total}  |  Completed: {completed}  |  Failed: {failed}",
            f"Review queue: {review_count} item(s) need attention",
        ]
        return "\n".join(lines)

    def _populate_table(self) -> None:
        table = self.query_one("#results-table", DataTable)
        table.add_columns(
            "Student",
            "Question",
            "Score",
            "Confidence",
            "Flags",
        )

        results_list = self.results.get("results", [])
        for r in results_list:
            student = r.get("student_name", "?")
            question = r.get("question_id", "?")
            score = r.get("score", 0)
            confidence = r.get("confidence", 0)
            flags = ", ".join(r.get("flags", [])) or "—"

            confidence_str = f"{confidence:.0%}" if isinstance(confidence, (int, float)) else str(confidence)
            table.add_row(
                student,
                question,
                str(score),
                confidence_str,
                flags,
            )

    @on(Button.Pressed, "#export-csv")
    def _export_csv(self) -> None:
        output_dir = Path("data/output/grades")
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(output_dir / f"grades_{timestamp}.csv")

        results_list = self.results.get("results", [])
        export_grades_csv(results_list, output_path, format_type="detailed")

        self.query_one("#summary", Static).update(
            f"{self._build_summary()}\nExported to: {output_path}"
        )

    @on(Button.Pressed, "#export-json")
    def _export_json(self) -> None:
        output_dir = Path("data/output/grades")
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(output_dir / f"grades_{timestamp}.json")

        results_list = self.results.get("results", [])
        export_grades_csv(results_list, output_path, format_type="json")

        self.query_one("#summary", Static).update(
            f"{self._build_summary()}\nExported to: {output_path}"
        )

    @on(Button.Pressed, "#done")
    def _on_done(self) -> None:
        self.app.pop_screen()
