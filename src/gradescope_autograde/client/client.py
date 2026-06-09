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

    def get_submission_content(
        self,
        course_id: str,
        assignment_id: str,
        submission_id: str,
    ) -> bytes:
        """GET the submission PDF as raw bytes.

        Gradescope stores submissions as PDF attachments on S3. The
        ``/pdf`` endpoint may 4xx, so we fetch the submission JSON and
        extract the S3 presigned URL from ``pdf_attachment.url``.
        """
        self._limiter.wait()
        # Fetch submission JSON to get the S3 presigned URL
        resp = self._session.get(
            f"/courses/{course_id}/assignments/{assignment_id}"
            f"/submissions/{submission_id}"
        )
        data = resp.json()
        pdf_attachment = data.get("pdf_attachment")
        pdf_url = pdf_attachment.get("url", "") if isinstance(pdf_attachment, dict) else ""
        if not pdf_url:
            # Try extracting text from submission JSON
            text = data.get("text", "") or data.get("content", "") or ""
            if text:
                return text.encode("utf-8")
            # Fallback: try /pdf endpoint
            try:
                self._limiter.wait()
                resp2 = self._session.get(
                    f"/courses/{course_id}/assignments/{assignment_id}"
                    f"/submissions/{submission_id}/pdf"
                )
                return resp2.content
            except Exception:
                # No retrievable content for this submission
                return b"[No retrievable content for this submission]"

        # Download PDF directly from S3 presigned URL
        import requests as _requests
        pdf_resp = _requests.get(pdf_url, timeout=60)
        pdf_resp.raise_for_status()
        return pdf_resp.content

    def submit_grade(
        self,
        course_id: str,
        assignment_id: str,
        submission_id: str,
        question_id: str,
        score: float,
        feedback: str = "",
    ) -> bool:
        """POST grade for a specific question. Returns True on success."""
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
