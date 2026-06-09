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

    def _log(self, msg: str, verbose: bool = False) -> None:
        if verbose:
            import sys
            print(f"[pipeline] {msg}", file=sys.stderr, flush=True)

    def run(
        self,
        course_id: str,
        assignment_id: str,
        rubric: dict,
        dry_run: bool = False,
        question_ids: list[str] | None = None,
        verbose: bool = False,
        upload: bool | None = None,
        with_pages: bool = False,
        log_func: callable | None = None,
    ) -> dict:
        """Run the full grading pipeline.

        Args:
            course_id: Gradescope course identifier.
            assignment_id: Gradescope assignment identifier.
            rubric: Rubric dict with a ``questions`` key containing a list of
                question dicts (each with ``id``, ``title``, ``max_points``,
                ``type``, ``rubric``, and optional ``extra_instructions``).
            dry_run: If ``True``, grade locally but do NOT submit to Gradescope.
                ``upload`` takes precedence when set.
            question_ids: Optional list of question IDs to grade (e.g. ``["q1",
                "q3"]``). When ``None`` (default), all questions are graded.
            verbose: If ``True``, include full traceback in error feedback and
                log step-by-step progress.
            upload: Explicit upload toggle. ``True`` = submit grades,
                ``False`` = dry-run only. When ``None`` (default), falls
                back to ``dry_run`` (``not dry_run``).
            with_pages: If ``True``, include ``[Page N of M]`` markers in
                extracted PDF text to help the LLM locate answers when
                students haven't mapped pages to questions.
            log_func: Optional callable for progress messages. Called with
                ``(msg, verbose)``. Defaults to ``print``.

        Returns:
            Summary dict with keys ``summary``, ``review_count``, and ``results``.
        """
        log = log_func or self._log
        submissions = self.client.list_submissions(course_id, assignment_id)
        self._progress["total"] = len(submissions)
        results: list[dict] = []
        log(f"Fetched {len(submissions)} submissions", verbose)

        for i, sub in enumerate(submissions):
            try:
                sub_id = sub.get("id", str(i))
                student_name = sub.get("student_name", f"Student {i}")

                # Fetch submission content
                log(f"[{i+1}/{len(submissions)}] Fetching PDF for {student_name}", verbose)
                content = self.client.get_submission_content(
                    course_id, assignment_id, sub_id
                )
                log(f"  PDF: {len(content)} bytes", verbose)

                # Extract text from content (handles PDF and plain text)
                answer_text = self._extract_answer(content, with_pages=with_pages)
                log(f"  Extracted {len(answer_text)} chars of text", verbose)

                question_results: list[dict] = []
                all_qs = rubric.get("questions", [])
                if question_ids:
                    all_qs = [q for q in all_qs if q.get("id") in question_ids]
                for question in all_qs:
                    qid = question.get("id", "?")
                    log(f"  Calling LLM for question {qid}...", verbose)
                    extra = question.get("extra_instructions", "")
                    result = self.engine.grade(question, answer_text, extra)
                    result["student_name"] = student_name
                    result["submission_id"] = sub_id
                    log(f"  → {qid}: score={result.get('score', '?')}, confidence={result.get('confidence', '?'):.0%}", verbose)
                    question_results.append(result)

                    # Check review queue
                    self.review_queue.check(sub_id, result)

                # Submit grades unless dry run
                should_upload = upload if upload is not None else not dry_run
                if should_upload:
                    log(f"  Uploading {len(question_results)} grades...", verbose)
                    for r in question_results:
                        self.client.submit_grade(
                            course_id,
                            assignment_id,
                            sub_id,
                            r["question_id"],
                            r["score"],
                            r.get("feedback", ""),
                        )
                    log(f"  Upload complete", verbose)
                else:
                    log(f"  Dry run — grades not uploaded", verbose)

                results.extend(question_results)
                self._progress["completed"] += 1

            except Exception as e:
                self._progress["failed"] += 1
                msg = f"Pipeline error: {e}"
                if verbose:
                    import traceback
                    msg = f"Pipeline error:\n{traceback.format_exc()}"
                log(f"  ERROR: {e}", verbose)
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

    def _extract_answer(self, content: bytes, with_pages: bool = False) -> str:
        """Extract text from submission content. Handles PDF and plain text.

        Args:
            content: Raw submission content bytes.
            with_pages: If ``True``, include ``[Page N of M]`` markers in
                extracted text for unmapped submissions.

        Returns:
            Extracted text string.
        """
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                import io

                import pymupdf

                doc = pymupdf.open(stream=content, filetype="pdf")
                if with_pages:
                    pages_text = []
                    total = len(doc)
                    for i, page in enumerate(doc):
                        page_num = i + 1
                        page_text = page.get_text().strip()
                        if page_text:
                            pages_text.append(f"[Page {page_num} of {total}]\n{page_text}")
                    doc.close()
                    return "\n\n".join(pages_text)
                text = "\n".join(page.get_text() for page in doc)
                doc.close()
                return text
            except Exception:
                return "[Could not extract text from submission]"

    @property
    def progress(self) -> dict:
        """Return a copy of the current progress counters."""
        return dict(self._progress)
