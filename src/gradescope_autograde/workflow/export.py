"""Export grading results to CSV, JSON, or review-queue formats."""

from __future__ import annotations

import csv
import json
from pathlib import Path


def export_grades_csv(
    results: list[dict],
    output_path: str,
    format_type: str = "gradescope",
) -> str:
    """Export grading results to a file.

    Args:
        results: List of grade result dicts.
        output_path: Destination file path.
        format_type: Output format — one of:

            - ``"gradescope"``: Gradescope-compatible CSV with columns
              Student Name, Student ID, Score.
            - ``"detailed"``: Full breakdown including per-question scores,
              confidence, flags, and feedback.
            - ``"json"``: Raw JSON dump of all results.

    Returns:
        The string path of the written file.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # -- JSON format --------------------------------------------------------
    if format_type == "json":
        path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
        return str(path)

    # -- Gradescope CSV format ----------------------------------------------
    if format_type == "gradescope":
        rows = []
        for r in results:
            rows.append(
                {
                    "Student Name": r.get("student_name", ""),
                    "Student ID": r.get("submission_id", ""),
                    "Score": r.get("score", 0),
                }
            )

        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["Student Name", "Student ID", "Score"]
            )
            writer.writeheader()
            writer.writerows(rows)

    # -- Detailed CSV format ------------------------------------------------
    elif format_type == "detailed":
        rows = []
        for r in results:
            row = {
                "Student Name": r.get("student_name", ""),
                "Submission ID": r.get("submission_id", ""),
                "Question ID": r.get("question_id", ""),
                "Score": r.get("score", 0),
                "Confidence": r.get("confidence", 0),
                "Flags": ", ".join(r.get("flags", [])),
                "Feedback": r.get("feedback", ""),
            }
            rows.append(row)

        with open(path, "w", newline="") as f:
            if rows:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)

    return str(path)


def export_review_queue(review_queue: object, output_path: str) -> str:
    """Export review queue items to JSON for human review.

    Args:
        review_queue: A :class:`ReviewQueue` instance (must have a ``pending``
            property returning a list of dicts).
        output_path: Destination file path.

    Returns:
        The string path of the written file.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(review_queue.pending, indent=2, ensure_ascii=False)
    )
    return str(path)
