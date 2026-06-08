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

            name = link.get_text(strip=True, separator=" ") or ""
            courses.append({"id": course_id, "name": name})

        return courses
    except Exception:
        return []


def _extract_gon_assignments(html: str) -> list[dict] | None:
    """Extract assignment list from Gradescope's embedded ``gon`` JSON data.

    Gradescope renders the full assignment list (active + completed) as
    JavaScript variables in a ``<script>`` tag on the ``/assignments`` page:
    ``gon.unversioned_assignments`` (active) and
    ``gon.ineligible_assignments`` (closed/completed).

    Returns a list of dicts with ``id`` and ``name`` keys, or ``None``
    if no gon data was found.
    """
    import json, re

    match = re.search(
        r"window\.gon\s*=\s*\{.*?gon\.(unversioned_assignments|ineligible_assignments)\s*=\s*(\[.*?\]);",
        html,
        re.DOTALL,
    )
    if not match:
        return None

    assignments: list[dict] = []
    seen: set[str] = set()

    for key in ("unversioned_assignments", "ineligible_assignments"):
        pattern = rf"gon\.{key}\s*=\s*(\[.*?\]);"
        m = re.search(pattern, html, re.DOTALL)
        if m:
            try:
                items = json.loads(m.group(1))
                for item in items:
                    aid = str(item.get("id", ""))
                    title = item.get("title") or ""
                    if aid and aid not in seen:
                        seen.add(aid)
                        assignments.append({"id": aid, "name": title})
            except json.JSONDecodeError:
                continue

    return assignments if assignments else None


def parse_assignments(html: str) -> list[dict]:
    """Extract assignment list from a Gradescope course page.

    Tries two strategies in order:
    1. **gon JSON data** — embedded ``<script>`` tag on the ``/assignments``
       page with the full list (active + completed). This is the preferred
       source because it includes closed assignments.
    2. **HTML anchor links** — fallback for the main course dashboard page
       which only shows the currently active assignment.
    """
    try:
        # Strategy 1: embedded gon JSON (full list, includes completed)
        result = _extract_gon_assignments(html)
        if result is not None:
            return result

        # Strategy 2: HTML anchor links (fallback, active only)
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

            name = link.get_text(strip=True, separator=" ") or ""
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

                name = link.get_text(strip=True, separator=" ") or ""
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
