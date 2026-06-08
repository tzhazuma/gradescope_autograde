import pytest

from gradescope_autograde.grader.rubric_parser import load_rubric


def test_load_example_rubric():
    rubric = load_rubric("config/rubrics/default_rubric.yaml")
    assert "questions" in rubric
    assert len(rubric["questions"]) > 0

def test_load_nonexistent():
    with pytest.raises(FileNotFoundError):
        load_rubric("nonexistent.yaml")
