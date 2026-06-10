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
        extraction: str = "auto",
        log_func: callable | None = None,
        gs_question_id: str | None = None,
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
            extraction: How to handle scanned/handwritten PDF submissions.
                ``"auto"`` (default): OCR for text models, multimodal for
                multimodal providers. ``"ocr"``: always OCR. ``"multimodal"``:
                render PDF pages as images and send to the LLM directly.
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
                    course_id, assignment_id, sub_id,
                    gs_question_id=gs_question_id,
                    student_name=student_name,
                )
                log(f"  PDF: {len(content)} bytes", verbose)

                question_results: list[dict] = []
                all_qs = rubric.get("questions", [])
                if question_ids:
                    all_qs = [q for q in all_qs if q.get("id") in question_ids]

                # Determine extraction approach
                use_multimodal = False
                if extraction == "multimodal":
                    use_multimodal = True
                elif extraction == "auto":
                    import gradescope_autograde.grader.providers.opencode_go as _og
                    use_multimodal = self.engine.provider.model in (
                        _og._MULTIMODAL_MODEL,
                    )

                # "text" mode: skip multimodal entirely
                if extraction == "text":
                    use_multimodal = False

                if use_multimodal:
                    # Render PDF pages as images for multimodal LLM
                    import io
                    import pymupdf
                    from PIL import Image

                    doc_mm = pymupdf.open(stream=content, filetype="pdf")
                    mm_images = []
                    for page in doc_mm:
                        pix = page.get_pixmap(dpi=150)
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                        buf = io.BytesIO()
                        img.save(buf, format="PNG")
                        mm_images.append(buf.getvalue())
                    doc_mm.close()
                    log(f"  Rendered {len(mm_images)} page image(s) for multimodal", verbose)

                    for question in all_qs:
                        qid = question.get("id", "?")
                        log(f"  Calling multimodal LLM for {qid}...", verbose)
                        extra = question.get("extra_instructions", "")
                        prompt = self._build_mm_prompt(question, extra)
                        raw = self.engine.provider.complete_multimodal(
                            prompt=prompt,
                            images=mm_images,
                            response_format="json",
                        )
                        import json as _json
                        try:
                            parsed = _json.loads(raw) if isinstance(raw, str) else raw
                        except Exception:
                            parsed = {"score": 0, "confidence": 0, "feedback": f"Parse error: {raw[:200]}", "flags": ["needs_review"]}
                        result = {
                            "question_id": qid,
                            "score": float(parsed.get("score", 0)),
                            "confidence": float(parsed.get("confidence", 0)),
                            "feedback": parsed.get("feedback", ""),
                            "flags": parsed.get("flags", []),
                        }
                        result["student_name"] = student_name
                        result["submission_id"] = sub_id
                        log(f"  → {qid}: score={result.get('score', '?')}, confidence={result.get('confidence', '?'):.0%}", verbose)
                        question_results.append(result)
                        self.review_queue.check(sub_id, result)
                else:
                    # Text extraction (with OCR fallback)
                    answer_text = self._extract_answer(content, with_pages=with_pages)
                    log(f"  Extracted {len(answer_text)} chars of text", verbose)

                    for question in all_qs:
                        qid = question.get("id", "?")
                        log(f"  Calling LLM for {qid}...", verbose)
                        extra = question.get("extra_instructions", "")
                        result = self.engine.grade(question, answer_text, extra)
                        result["student_name"] = student_name
                        result["submission_id"] = sub_id
                        log(f"  → {qid}: score={result.get('score', '?')}, confidence={result.get('confidence', '?'):.0%}", verbose)
                        question_results.append(result)
                        self.review_queue.check(sub_id, result)

                    # Check review queue
                    self.review_queue.check(sub_id, result)

                # Submit grades unless dry run
                should_upload = upload if upload is not None else not dry_run
                if should_upload:
                    # Build the question -> GS question ID mapping
                    if gs_question_id:
                        gs_qid_map = {q.get("id"): gs_question_id for q in all_qs}
                    else:
                        gs_qid_map = {}

                    # Build student name → QS ID mapping from the question page
                    if gs_question_id:
                        try:
                            qs_map = self.client.get_question_submissions_map(
                                course_id, gs_question_id
                            )
                        except Exception:
                            qs_map = {}
                    else:
                        qs_map = {}

                    upload_count = 0
                    skip_count = 0
                    for r in question_results:
                        flags = r.get("flags", [])
                        if any(f in flags for f in ("pipeline_error", "content_error", "extraction_error", "parse_error")):
                            skip_count += 1
                            log(f"  Skipping {r.get('student_name','?')}/{r.get('question_id','?')} — has errors", verbose)
                            continue
                        rid = r.get("question_id", "")
                        gsid = gs_qid_map.get(rid, rid)
                        sname = r.get("student_name", "")
                        # Find question submission ID from the mapping
                        qs_id = ""
                        for full_name, qsid in qs_map.items():
                            if full_name.startswith(sname):
                                qs_id = qsid
                                break
                        if not qs_id:
                            qs_id = r.get("submission_id", "")
                        self.client.submit_grade(
                            course_id,
                            assignment_id,
                            qs_id,
                            gsid,
                            r["score"],
                            r.get("feedback", ""),
                        )
                        upload_count += 1
                    log(f"  Uploaded {upload_count}, skipped {skip_count} (errors)", verbose)
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

    @staticmethod
    def _render_pdf_as_images(content: bytes, dpi: int = 150) -> list[bytes]:
        """Render PDF pages as PNG images for multimodal input."""
        import io
        import pymupdf
        from PIL import Image

        doc = pymupdf.open(stream=content, filetype="pdf")
        images = []
        for page in doc:
            pix = page.get_pixmap(dpi=dpi)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            images.append(buf.getvalue())
        doc.close()
        return images

    def _extract_answer(self, content: bytes, with_pages: bool = False) -> str:
        """Extract text from submission content. Handles PDF and plain text.

        For scanned/image PDFs where PyMuPDF returns minimal text, falls
        back to OCR via pytesseract.

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
            pass

        # Try PyMuPDF text extraction
        import io
        import pymupdf

        try:
            doc = pymupdf.open(stream=content, filetype="pdf")
            pages_text_all = []
            total = len(doc)
            for i, page in enumerate(doc):
                page_text = page.get_text().strip()
                pages_text_all.append(page_text)
            doc.close()

            combined = "\n".join(pages_text_all)
            word_count = len(combined.split())

            # If PyMuPDF extracted enough text, return it directly
            if word_count > 20:
                if with_pages:
                    result = []
                    for i, pt in enumerate(pages_text_all):
                        if pt.strip():
                            result.append(f"[Page {i+1} of {total}]\n{pt}")
                    return "\n\n".join(result) if result else combined
                return combined

            # PyMuPDF extracted too little text — try OCR
            try:
                import pytesseract
                from PIL import Image

                doc2 = pymupdf.open(stream=content, filetype="pdf")
                ocr_pages = []
                for i, page in enumerate(doc2):
                    pix = page.get_pixmap(dpi=200)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    page_ocr = pytesseract.image_to_string(img, lang="eng")
                    ocr_pages.append(page_ocr.strip())

                    if with_pages:
                        ocr_pages[-1] = f"[Page {i+1} of {total}]\n{ocr_pages[-1]}"
                doc2.close()
                result = "\n\n".join(p for p in ocr_pages if p)
                return result if result else combined
            except ImportError:
                return combined  # OCR not available, return whatever PyMuPDF got
            except Exception:
                return combined  # OCR failed, return whatever PyMuPDF got
        except Exception:
            return "[Could not extract text from submission]"

    @property
    def progress(self) -> dict:
        """Return a copy of the current progress counters."""
        return dict(self._progress)

    @staticmethod
    def _build_mm_prompt(question: dict, extra_instructions: str = "") -> str:
        qid = question.get("id", "?")
        title = question.get("title", f"Question {qid}")
        max_pts = question.get("max_points", 10)
        rubric_text = "\n".join(
            f"  - {c.get('name', c.get('criterion', ''))}: {c.get('points', 0)} pts"
            for c in question.get("rubric", [])
        )
        # Try loading multimodal prompt from file, fall back to default
        from pathlib import Path as _P
        prompt_file = _P(__file__).parent.parent.parent.parent / "prompts" / "grading_multimodal.txt"
        if prompt_file.exists():
            template = prompt_file.read_text(encoding="utf-8")
        else:
            template = (
                "GRADING TASK\n\n"
                "Question: {title} ({max_pts} points max)\n\n"
                "RUBRIC:\n{rubric_text}\n\n"
                "The student's handwritten answer is shown in the image(s). Evaluate it against the rubric.\n\n"
                "{extra}\n"
                "Output JSON: "
                '{{"score": <total points>, "confidence": 0.0-1.0, '
                '"feedback": "<brief>", "flags": []}}'
            )
        extra = f"ADDITIONAL INSTRUCTIONS:\n{extra_instructions}" if extra_instructions else ""
        return template.format(
            title=title, max_pts=max_pts, rubric_text=rubric_text, extra=extra,
        )
