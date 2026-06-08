from pathlib import Path

import pytest


@pytest.fixture
def project_root():
    return Path(__file__).parent.parent

@pytest.fixture
def sample_rubric():
    return {
        "assignment_title": "Test HW",
        "total_points": 100,
        "questions": [
            {
                "id": "q1",
                "title": "Test Question",
                "max_points": 10,
                "type": "short_answer",
                "rubric": [
                    {"name": "Correct answer", "points": 5, "description": ""},
                    {"name": "Explanation", "points": 5, "description": ""},
                ],
            }
        ],
        "grading_guidelines": ["Be fair"],
    }
