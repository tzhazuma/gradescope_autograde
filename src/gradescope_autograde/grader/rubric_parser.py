"""Rubric loader — supports YAML, PDF, and LaTeX formats."""

from __future__ import annotations

from pathlib import Path

import yaml


def _rubric_from_parsed_questions(questions: list[dict]) -> dict:
    """Convert parsed question dicts (from PDF/LaTeX) to a rubric dict."""
    rubric_questions = []
    for q in questions:
        qnum = q.get("question_number", 1)
        rubric_questions.append({
            "id": f"q{qnum}",
            "title": q.get("title", f"Question {qnum}"),
            "max_points": q.get("max_points", 10.0),
            "type": "short_answer",
            "text": q.get("text", ""),
            "reference_answer": q.get("reference_answer", ""),
            "rubric": [
                {
                    "name": "correctness",
                    "points": q.get("max_points", 10.0),
                    "description": "Answer is correct and complete",
                }
            ],
        })

    return {
        "questions": rubric_questions,
        "grading_guidelines": [
            "Award partial credit when the student shows understanding but makes minor errors",
        ],
    }


def load_rubric(path: str | Path, default_points: float = 10.0) -> dict:
    """Load a rubric from a YAML, PDF, or LaTeX file.

    Supported formats (auto-detected by file extension):

    - ``.yaml`` / ``.yml`` — parsed as YAML directly.
    - ``.pdf`` — questions extracted via :func:`parse_reference_pdf`.
    - ``.tex`` — questions extracted via :func:`parse_reference_tex`.

    Args:
        path: Path to the rubric file.
        default_points: Default max points per question when parsing
            PDF or LaTeX (ignored for YAML).

    Returns:
        A rubric dict with at least a ``"questions"`` key.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Rubric file not found: {p}")

    suffix = p.suffix.lower()

    if suffix in (".yaml", ".yml"):
        with p.open() as f:
            rubric = yaml.safe_load(f)

        if not isinstance(rubric, dict):
            raise ValueError("Rubric must be a YAML mapping (dict)")
        if "questions" not in rubric:
            raise ValueError("Rubric must contain a 'questions' key")
        if not isinstance(rubric["questions"], list):
            raise ValueError("'questions' must be a list")
        return rubric

    if suffix == ".pdf":
        from gradescope_autograde.grader.pdf_parser import parse_reference_pdf

        questions = parse_reference_pdf(str(p))
        return _rubric_from_parsed_questions(questions)

    if suffix == ".tex":
        from gradescope_autograde.grader.latex_parser import parse_reference_tex

        questions = parse_reference_tex(str(p))
        return _rubric_from_parsed_questions(questions)

    raise ValueError(
        f"Unsupported rubric format: {suffix}. "
        f"Expected .yaml, .yml, .pdf, or .tex"
    )


def parse_questions(rubric: dict) -> list[dict]:
    questions: list[dict] = []

    for idx, q in enumerate(rubric["questions"]):
        if not isinstance(q, dict):
            raise ValueError(f"Question at index {idx} must be a mapping")

        question_id = q.get("id", f"q{idx + 1}")
        question_title = q.get("title", q.get("question", q.get("text", "")))
        max_points = float(q.get("max_points", q.get("points", 0)))
        criteria = q.get("rubric", q.get("criteria", []))
        extra_instructions = q.get("extra_instructions", "")

        if not isinstance(criteria, list):
            raise ValueError(f"Rubric/criteria for question {question_id} must be a list")

        parsed_rubric: list[dict] = []
        for c in criteria:
            if isinstance(c, str):
                parsed_rubric.append({"name": c, "points": 0, "description": ""})
            elif isinstance(c, dict):
                parsed_rubric.append({
                    "name": c.get("name", c.get("criterion", c.get("description", ""))),
                    "points": float(c.get("points", 0)),
                    "description": c.get("description", ""),
                })

        questions.append({
            "id": question_id,
            "title": question_title,
            "max_points": max_points,
            "type": q.get("type", "short_answer"),
            "rubric": parsed_rubric,
            "extra_instructions": extra_instructions,
        })

    return questions


def list_rubric_questions(path: str | Path) -> list[dict]:
    """Load a rubric and return its questions list (for display/selection).

    Each question dict contains ``id``, ``title``, ``max_points``, and
    ``type`` keys. This is a lightweight alternative to :func:`load_rubric`
    that does not parse PDF or LaTeX files — only YAML/yml.
    """
    p = Path(path)
    if p.suffix.lower() not in (".yaml", ".yml"):
        return []
    rubric = load_rubric(str(p))
    return parse_questions(rubric)
