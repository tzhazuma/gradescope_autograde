"""HTML parsing utilities for Gradescope pages.

Gradescope serves data as HTML tables and cards, not a JSON API.
All parsers return raw dicts for flexibility; the caller decides
what to do with them.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup


def parse_courses(html: str) -> list[dict]:
    """Extract course list from the Gradescope dashboard HTML.

    Looks for links matching ``/courses/<id>`` and extracts the course
    number/name from the surrounding element text.
    """
    try:
        soup = BeautifulSoup(html, "html.parser")
        courses: list[dict] = []
        seen: set[str] = set()

        for link in soup.find_all("a", href=re.compile(r"/courses/\d+")):
            href = link.get("href", "")
            match = re.search(r"/courses/(\d+)", href)
            if not match:
                continue
            course_id = match.group(1)
            if course_id in seen:
                continue
            seen.add(course_id)

            name = link.get_text(strip=True) or ""
            courses.append({"id": course_id, "name": name})

        return courses
    except Exception:
        return []


def parse_assignments(html: str) -> list[dict]:
    """Extract assignment list from a Gradescope course page.

    Gradescope renders assignments as table rows or assignment cards.
    Each row typically contains the assignment name, deadline, and
    a link to the assignment page.
    """
    try:
        soup = BeautifulSoup(html, "html.parser")
        assignments: list[dict] = []
        seen: set[str] = set()

        for link in soup.find_all("a", href=re.compile(r"/assignments/\d+")):
            href = link.get("href", "")
            match = re.search(r"/assignments/(\d+)", href)
            if not match:
                continue
            assignment_id = match.group(1)
            if assignment_id in seen:
                continue
            seen.add(assignment_id)

            name = link.get_text(strip=True) or ""
            assignments.append({"id": assignment_id, "name": name})

        if not assignments:
            for link in soup.find_all(
                "a", href=re.compile(r"/courses/\d+/assignments/\d+")
            ):
                href = link.get("href", "")
                match = re.search(r"/assignments/(\d+)", href)
                if not match:
                    continue
                assignment_id = match.group(1)
                if assignment_id in seen:
                    continue
                seen.add(assignment_id)

                name = link.get_text(strip=True) or ""
                assignments.append({"id": assignment_id, "name": name})

        return assignments
    except Exception:
        return []


def parse_submissions(html: str) -> list[dict]:
    """Extract submission list from a Gradescope review grades page.

    Parses the HTML table that Gradescope renders for submission review.
    Each row typically has: student name/email, submission time, score,
    and a link to the individual submission.
    """
    try:
        soup = BeautifulSoup(html, "html.parser")
        submissions: list[dict] = []

        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 2:
                continue

            link = row.find("a", href=re.compile(r"/submissions/\d+"))
            submission_id = ""
            if link:
                href = link.get("href", "")
                match = re.search(r"/submissions/(\d+)", href)
                if match:
                    submission_id = match.group(1)

            if not submission_id:
                continue

            cell_texts = [c.get_text(strip=True) for c in cells]
            student_name = cell_texts[0] if cell_texts else ""
            student_email = cell_texts[1] if len(cell_texts) > 1 else ""
            submitted_at = cell_texts[2] if len(cell_texts) > 2 else ""
            score = cell_texts[3] if len(cell_texts) > 3 else ""

            submissions.append({
                "id": submission_id,
                "student_name": student_name,
                "student_email": student_email,
                "submitted_at": submitted_at,
                "score": score,
            })

        return submissions
    except Exception:
        return []
