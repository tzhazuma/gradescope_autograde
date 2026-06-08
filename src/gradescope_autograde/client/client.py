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
        """GET /courses/{course_id} → parse assignment list."""
        self._limiter.wait()
        resp = self._session.get(f"/courses/{course_id}")
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

    def get_submission_content(
        self,
        course_id: str,
        assignment_id: str,
        submission_id: str,
    ) -> bytes:
        """GET the submission PDF as raw bytes."""
        self._limiter.wait()
        resp = self._session.get(
            f"/courses/{course_id}/assignments/{assignment_id}"
            f"/submissions/{submission_id}/pdf"
        )
        return resp.content

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
