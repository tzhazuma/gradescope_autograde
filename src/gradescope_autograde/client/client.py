"""Gradescope HTTP client for programmatic interaction."""

from __future__ import annotations

from ..transport.exceptions import GradescopeAPIError
from ..transport.session import GSSession
from .parser import parse_assignments, parse_courses, parse_submissions
from .ratelimit import RateLimiter


class GSClient:
    """High-level client for Gradescope operations.

    Wraps a :class:`GSSession` to provide methods for listing courses,
    assignments, and submissions, fetching submission content, and
    uploading grades.  All requests are rate-limited automatically.
    """

    def __init__(self, session: GSSession):
        self._session = session
        self._limiter = RateLimiter(delay=session.request_delay)

    def list_courses(self) -> list[dict]:
        """GET / → parse dashboard for course list."""
        self._limiter.wait()
        resp = self._session.get("/")
        return parse_courses(resp.text)

    def list_assignments(self, course_id: str) -> list[dict]:
        """GET /courses/{course_id}/assignments → parse assignment list.

        Uses the dedicated assignments page which includes both active and
        completed assignments via embedded ``gon`` JSON data.
        """
        self._limiter.wait()
        resp = self._session.get(f"/courses/{course_id}/assignments")
        return parse_assignments(resp.text)

    def list_submissions(
        self, course_id: str, assignment_id: str
    ) -> list[dict]:
        """GET /courses/{course_id}/assignments/{assignment_id}/review_grades."""
        self._limiter.wait()
        resp = self._session.get(
            f"/courses/{course_id}/assignments/{assignment_id}/review_grades"
        )
        return parse_submissions(resp.text)

    def list_questions(self, course_id: str, assignment_id: str) -> list[dict]:
        """Extract question/score column names from the review grades table.

        Returns a list of dicts with ``id`` (numeric) and ``name`` (header text).
        Falls back to an empty list when the page has no per‑question columns.
        """
        self._limiter.wait()
        resp = self._session.get(
            f"/courses/{course_id}/assignments/{assignment_id}/review_grades"
        )
        from bs4 import BeautifulSoup
        import re

        soup = BeautifulSoup(resp.text, "html.parser")
        questions: list[dict] = []

        # Score columns in the table are typically rendered as <td> with question
        # scores.  We detect them by looking at the second data row's <td> cells
        # and mapping back to <th> headers.
        #
        # Simpler heuristic: collect <th> cells that look like question titles
        # (short text, not generic headers).
        for th in soup.find_all("th"):
            text = th.get_text(strip=True)
            if not text:
                continue
            low = text.lower().strip()
            # Skip generic column headers
            skip = {"name", "email", "score", "status", "submission", "submitted",
                    "student", "id", "view", "action", "points possible", "total",
                    "late", "time", "date", "graded?", "viewed?", "time (cst)",
                    "time (pst)", "time (est)", "points", "overall score"}
            if low in skip or low.startswith("score/") or low.startswith("total"):
                continue
            if len(text) > 60:
                continue
            # Must contain at least one letter (not purely numeric)
            if not re.search(r'[a-zA-Z]', text):
                continue
            questions.append({"id": f"q{len(questions)+1}", "name": text})

        return questions

    def list_assignment_questions(self, course_id: str, assignment_id: str) -> list[dict]:
        """Fetch the question list for an assignment.

        Tries to find question IDs by checking the per-question submissions
        page. Returns a list of dicts with ``id``, ``gs_id``, ``title``, ``position``.
        """
        import json, re as _re2
        from bs4 import BeautifulSoup

        found_qid = None
        # Probe a small set of candidate IDs (typically sequential around known bases)
        aid = int(assignment_id)
        import time as _time
        for qid_candidate in [aid * 10 + 1, aid * 9 + 1, aid * 8 + 1,
                               71029765, 52000001, 33000001]:
            _time.sleep(0.3)
            try:
                qresp = self._session.get(
                    f"/courses/{course_id}/questions/{qid_candidate}/submissions",
                    timeout=5,
                )
                if qresp.status_code == 200 and "submission" in qresp.text.lower()[:500]:
                    found_qid = str(qid_candidate)
                    break
            except Exception:
                continue

        if not found_qid:
            return []

        # Now access this question's grade page to get the switcher data
        # Need a submission ID first
        try:
            rg = self._session.get(
                f"/courses/{course_id}/assignments/{assignment_id}/review_grades"
            )
            rg_soup = BeautifulSoup(rg.text, "html.parser")
            sub_link = rg_soup.find("a", href=_re2.compile(r"/submissions/\d+"))
            if not sub_link:
                return []
            sid = _re2.search(r"/submissions/(\d+)", sub_link["href"]).group(1)
        except Exception:
            return []

        # Get the question submissions map for this question to get a QS ID
        qs_map = self.get_question_submissions_map(course_id, found_qid)
        qs_id = next(iter(qs_map.values())) if qs_map else ""

        if not qs_id:
            return []

        # Access the grade page with the found QS ID
        try:
            qresp = self._session.get(
                f"/courses/{course_id}/questions/{found_qid}/submissions/{qs_id}/grade"
            )
            soup = BeautifulSoup(qresp.text, "html.parser")
            grader = soup.find(attrs={"data-react-class": "SubmissionGrader"})
            if grader:
                raw = grader.get("data-react-props", "{}").replace("&quot;", '"')
                props = json.loads(raw)
                qs = props.get("question_switcher_presenter", {})
                if isinstance(qs, dict):
                    qid_to_title = qs.get("question_id_to_title", {})
                    qid_to_link = qs.get("question_id_to_link", {})
                    questions = []
                    for qid_str, title_label in qid_to_title.items():
                        pos = title_label.split(":")[0].strip() if ":" in title_label else "?"
                        title = title_label.split(":")[-1].strip() if ":" in title_label else title_label
                        simple_id = f"q{pos}" if pos.isdigit() else title.lower()
                        questions.append({
                            "id": simple_id, "gs_id": qid_str,
                            "title": title,
                            "position": int(pos) if pos.isdigit() else 0,
                            "link": qid_to_link.get(qid_str, ""),
                        })
                    return questions
        except Exception:
            pass
        return []

    def get_submission_content(
        self,
        course_id: str,
        assignment_id: str,
        submission_id: str,
        gs_question_id: str | None = None,
        student_name: str = "",
    ) -> bytes:
        """GET the submission PDF/Image content as raw bytes.

        Handles three content types in order:
        1. PDF attachments (``pdf_attachment.url``)
        2. Image uploads (via question-specific grading page)
        3. Plain text
        4. ``/pdf`` endpoint fallback

        Args:
            gs_question_id: Numeric question ID for image-based submissions.
            student_name: Student name for QS ID lookup.
        """
        self._limiter.wait()
        # Fetch submission JSON
        resp = self._session.get(
            f"/courses/{course_id}/assignments/{assignment_id}"
            f"/submissions/{submission_id}"
        )
        data = resp.json()
        pdf_attachment = data.get("pdf_attachment")
        pdf_url = pdf_attachment.get("url", "") if isinstance(pdf_attachment, dict) else ""
        if pdf_url:
            import requests as _requests
            pdf_resp = _requests.get(pdf_url, timeout=60)
            pdf_resp.raise_for_status()
            return pdf_resp.content

        # No PDF — try image attachments via question page
        if gs_question_id:
            try:
                # Get the QS ID for this student
                qs_map = self.get_question_submissions_map(course_id, gs_question_id)
                qs_id = ""
                for full_name, qsid in qs_map.items():
                    if full_name.startswith(student_name):
                        qs_id = qsid
                        break
                if qs_id:
                    import json, io
                    from bs4 import BeautifulSoup
                    import pymupdf
                    from PIL import Image

                    qresp = self._session.get(
                        f"/courses/{course_id}/questions/{gs_question_id}/submissions/{qs_id}/grade"
                    )
                    soup = BeautifulSoup(qresp.text, "html.parser")
                    grader = soup.find(attrs={"data-react-class": "SubmissionGrader"})
                    if grader:
                        raw = grader.get("data-react-props", "").replace("&quot;", '"')
                        props = json.loads(raw)
                        pages = props.get("pages", [])
                        if pages:
                            # Download images and combine into a PDF
                            import requests as _req
                            doc = pymupdf.open()
                            for p in pages:
                                img_url = p.get("url", "")
                                if not img_url:
                                    continue
                                try:
                                    img_resp = _req.get(img_url, timeout=30)
                                    img_resp.raise_for_status()
                                    img_bytes = img_resp.content
                                    img_pil = Image.open(io.BytesIO(img_bytes))
                                    # Convert PIL Image to RGB if needed
                                    if img_pil.mode != "RGB":
                                        img_pil = img_pil.convert("RGB")
                                    img_bytes_rgb = io.BytesIO()
                                    img_pil.save(img_bytes_rgb, format="PNG")
                                    # Add as PDF page
                                    page = doc.new_page(width=img_pil.width, height=img_pil.height)
                                    page.insert_image(
                                        page.rect, stream=img_bytes_rgb.getvalue()
                                    )
                                except Exception:
                                    continue
                            pdf_bytes = doc.tobytes()
                            doc.close()
                            if len(pdf_bytes) > 100:
                                return pdf_bytes
            except Exception:
                pass

        # Try plain text
        text = data.get("text", "") or data.get("content", "") or ""
        if text:
            return text.encode("utf-8")

        # Fallback: /pdf endpoint
        try:
            self._limiter.wait()
            resp2 = self._session.get(
                f"/courses/{course_id}/assignments/{assignment_id}"
                f"/submissions/{submission_id}/pdf"
            )
            return resp2.content
        except Exception:
            return b"[No retrievable content for this submission]"

    def _get_csrf_and_save_url(
        self, course_id: str, question_id: str, submission_id: str
    ) -> tuple[str, str, str, str, float]:
        """Fetch grading context to extract CSRF token and save_grade URL.

        Returns ``(csrf_token, save_url, base_url, scoring_type, max_points)``.
        Raises ``ValueError`` if the page is inaccessible.
        """
        import json
        from bs4 import BeautifulSoup

        url = f"/courses/{course_id}/questions/{question_id}/submissions/{submission_id}/grade"
        resp = self._session.get(url)
        soup = BeautifulSoup(resp.text, "html.parser")
        csrf_meta = soup.find("meta", {"name": "csrf-token"})
        csrf_token = csrf_meta.get("content", "") if csrf_meta else ""
        save_url, scoring_type, max_points = "", "negative", 0.0
        grader = soup.find(attrs={"data-react-class": "SubmissionGrader"})
        if grader:
            props = json.loads(grader.get("data-react-props", "{}"))
            save_url = props.get("urls", {}).get("save_grade", "")
            scoring_type = (
                props.get("assignment", {})
                .get("settings", {})
                .get("question_settings", {})
                .get("scoring_type", "negative")
            )
            max_points = float(
                props.get("question", {}).get("weight", 0) or 0
            )
        base = self._session.base_url if hasattr(self._session, 'base_url') else "https://www.gradescope.com"
        return csrf_token, save_url, base, scoring_type, max_points

    def get_question_submissions_map(
        self, course_id: str, question_id: str
    ) -> dict[str, str]:
        """Fetch the mapping of student names → question submission IDs.

        Parses the per-question submissions table at
        ``/courses/{cid}/questions/{qid}/submissions``.

        Returns a dict like ``{"康子健": "3951769803", "姚鉴轩": "3951769804", ...}``
        """
        import re as _re3
        from bs4 import BeautifulSoup

        resp = self._session.get(
            f"/courses/{course_id}/questions/{question_id}/submissions"
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        mapping: dict[str, str] = {}

        # Look for grade links in the submissions table
        for link in soup.find_all("a", href=_re3.compile(
            rf"/courses/{course_id}/questions/{question_id}/submissions/\d+/grade"
        )):
            qsid = _re3.search(r"/submissions/(\d+)/grade", link["href"]).group(1)
            # The link text is typically the student name
            name = link.get_text(strip=True)
            if name and qsid:
                mapping[name] = qsid

        return mapping

    def submit_grade(
        self,
        course_id: str,
        assignment_id: str,
        submission_id: str,
        question_id: str,
        score: float,
        feedback: str = "",
    ) -> bool:
        """POST grade for a specific question. Returns True on success.

        Uses the Gradescope React grading endpoint:
        ``/courses/{cid}/questions/{qid}/submissions/{qsid}/grade``
        with CSRF token extracted from the page.

        Automatically detects scoring type (positive/negative) and adjusts
        the point value accordingly.

        **Scoring logic** (no rubric items applied):
        - ``negative`` (deduction): default = max_points (full credit).
          Adjustment = score - max_points.  GS computes:
          ``result = max(0, min(max, max_points + adjustment))``.
        - ``positive`` (addition): default = 0.  GS computes:
          ``result = rubric_item_sum + points``.
        """
        import json

        self._limiter.wait()
        try:
            csrf, save_url, base_url, scoring_type, max_pts = self._get_csrf_and_save_url(
                course_id, question_id, submission_id
            )
        except Exception:
            # Fallback: try old /assignments/{aid}/submissions/{sid}/grade endpoint
            self._limiter.wait()
            resp = self._session.post(
                f"/courses/{course_id}/assignments/{assignment_id}"
                f"/submissions/{submission_id}/grade",
                data={
                    "question_id": question_id,
                    "score": str(score),
                    "feedback": feedback,
                },
            )
            return resp.status_code == 200

        if not save_url or not csrf:
            return False

        # In negative scoring mode, points are treated as adjustment (deduction).
        # Convert the desired score to the appropriate point value.
        #   negative: score = max_pts - deductions + adjustment
        #   positive: score = rubric_total + adjustment
        # With no rubric items applied, we send the score directly.
        if scoring_type == "negative" and max_pts > 0:
            points_to_send = score - max_pts  # e.g. 15 - 20 = -5 adjustment
        else:
            points_to_send = score

        payload = {
            "question_submission_evaluation": {
                "points": points_to_send,
                "comments": feedback or "",
            }
        }
        headers = {
            "X-CSRF-Token": csrf,
            "Content-Type": "application/json",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
        }
        try:
            self._limiter.wait()
            resp = self._session._session.post(
                f"{base_url}{save_url}",
                json=payload,
                headers=headers,
            )
            return resp.status_code == 200
        except Exception:
            return False
