"""Workflow pipeline — orchestrates fetch → grade → review → export."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


class Pipeline:
    """Coordinates GSClient + GradingEngine + ReviewQueue for full grading runs.

    Args:
        client: GSClient instance for Gradescope API operations.
        engine: GradingEngine instance for LLM-based grading.
        review_queue: ReviewQueue instance for flagging uncertain results.
        config: Optional configuration dict (reserved for future use).
    """

    def __init__(
        self,
        client: Any,
        engine: Any,
        review_queue: Any,
        config: dict | None = None,
    ) -> None:
        self.client = client
        self.engine = engine
        self.review_queue = review_queue
        self.config = config or {}
        self._progress: dict[str, int] = {
            "completed": 0,
            "reviewed": 0,
            "failed": 0,
            "total": 0,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        course_id: str,
        assignment_id: str,
        rubric: dict,
        dry_run: bool = False,
        question_ids: list[str] | None = None,
        verbose: bool = False,
    ) -> dict:
        """Run the full grading pipeline.

        Args:
            course_id: Gradescope course identifier.
            assignment_id: Gradescope assignment identifier.
            rubric: Rubric dict with a ``questions`` key containing a list of
                question dicts (each with ``id``, ``title``, ``max_points``,
                ``type``, ``rubric``, and optional ``extra_instructions``).
            dry_run: If ``True``, grade locally but do NOT submit to Gradescope.
            question_ids: Optional list of question IDs to grade (e.g. ``["q1",
                "q3"]``). When ``None`` (default), all questions are graded.
            verbose: If ``True``, include full traceback in error feedback.

        Returns:
            Summary dict with keys ``summary``, ``review_count``, and ``results``.
        """
        submissions = self.client.list_submissions(course_id, assignment_id)
        self._progress["total"] = len(submissions)
        results: list[dict] = []

        for i, sub in enumerate(submissions):
            try:
                sub_id = sub.get("id", str(i))
                student_name = sub.get("student_name", f"Student {i}")

                # Fetch submission content
                content = self.client.get_submission_content(
                    course_id, assignment_id, sub_id
                )

                # Extract text from content (handles PDF and plain text)
                answer_text = self._extract_answer(content)

                question_results: list[dict] = []
                all_qs = rubric.get("questions", [])
                if question_ids:
                    all_qs = [q for q in all_qs if q.get("id") in question_ids]
                for question in all_qs:
                    extra = question.get("extra_instructions", "")
                    result = self.engine.grade(question, answer_text, extra)
                    result["student_name"] = student_name
                    result["submission_id"] = sub_id
                    question_results.append(result)

                    # Check review queue
                    self.review_queue.check(sub_id, result)

                # Submit grades unless dry run
                if not dry_run:
                    for r in question_results:
                        self.client.submit_grade(
                            course_id,
                            assignment_id,
                            sub_id,
                            r["question_id"],
                            r["score"],
                            r.get("feedback", ""),
                        )

                results.extend(question_results)
                self._progress["completed"] += 1

            except Exception as e:
                self._progress["failed"] += 1
                msg = f"Pipeline error: {e}"
                if verbose:
                    import traceback
                    msg = f"Pipeline error:\n{traceback.format_exc()}"
                results.append(
                    {
                        "submission_id": sub.get("id", str(i)),
                        "student_name": sub.get("student_name", f"Student {i}"),
                        "question_id": "error",
                        "score": 0,
                        "confidence": 0,
                        "feedback": msg,
                        "flags": ["needs_review", "pipeline_error"],
                    }
                )

        return {
            "summary": self._progress,
            "review_count": self.review_queue.count,
            "results": results,
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _extract_answer(self, content: bytes) -> str:
        """Extract text from submission content. Handles PDF and plain text."""
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                import io

                import pymupdf

                doc = pymupdf.open(stream=content, filetype="pdf")
                text = "\n".join(page.get_text() for page in doc)
                doc.close()
                return text
            except Exception:
                return "[Could not extract text from submission]"

    @property
    def progress(self) -> dict:
        """Return a copy of the current progress counters."""
        return dict(self._progress)
