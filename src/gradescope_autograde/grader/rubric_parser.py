"""Rubric YAML loader and parser."""

from __future__ import annotations

from pathlib import Path

import yaml


def load_rubric(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Rubric file not found: {p}")
    if p.suffix not in (".yaml", ".yml"):
        raise ValueError(f"Expected .yaml or .yml file, got: {p.suffix}")

    with p.open() as f:
        rubric = yaml.safe_load(f)

    if not isinstance(rubric, dict):
        raise ValueError("Rubric must be a YAML mapping (dict)")

    if "questions" not in rubric:
        raise ValueError("Rubric must contain a 'questions' key")

    if not isinstance(rubric["questions"], list):
        raise ValueError("'questions' must be a list")

    return rubric


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
