from gradescope_autograde.models import (
    Assignment,
    Course,
    Criterion,
    GradeResult,
    GradingRubric,
    LLMModel,
    PDFQuestion,
    ProviderType,
    Question,
)


def test_course_model():
    c = Course(id="123", name="CS101", role="instructor")
    assert c.id == "123"
    assert c.name == "CS101"

def test_assignment_model():
    a = Assignment(id="a1", course_id="123", title="HW1", points=100)
    assert a.title == "HW1"
    assert a.submission_type == "pdf"

def test_llmmodel_no_warning():
    """Verify model_id field works without Pydantic warning."""
    m = LLMModel(
        provider=ProviderType.OPENCODE_GO,
        model_id="deepseek-v4-flash",
        display_name="DeepSeek V4 Flash",
        context_length=1000000,
    )
    assert m.model_id == "deepseek-v4-flash"
    assert m.provider == ProviderType.OPENCODE_GO

def test_pdf_question():
    q = PDFQuestion(
        question_number=1, text="What is recursion?", reference_answer="A function calling itself"
    )
    assert q.question_number == 1
    assert q.max_points == 10.0

def test_grading_rubric():
    rubric = GradingRubric(
        assignment_title="HW1",
        total_points=100,
        questions=[
            Question(id="q1", title="Q1", max_points=10, rubric=[
                Criterion(name="Correct", points=10)
            ])
        ]
    )
    assert len(rubric.questions) == 1
    assert rubric.questions[0].rubric[0].name == "Correct"

def test_grade_result_confidence_bounds():
    import pytest
    from pydantic import ValidationError
    r = GradeResult(question_id="q1", score=8, confidence=0.85)
    assert r.confidence == 0.85
    with pytest.raises(ValidationError):
        GradeResult(question_id="q1", score=8, confidence=1.5)
