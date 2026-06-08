from pydantic import BaseModel

class Criterion(BaseModel):
    name: str
    points: float
    description: str = ""

class Question(BaseModel):
    id: str
    title: str
    max_points: float
    type: str = "short_answer"  # "short_answer" | "essay" | "multiple_choice" | "code"
    rubric: list[Criterion] = []
    extra_instructions: str = ""  # Additional grading notes from instructor

class GradingRubric(BaseModel):
    assignment_title: str
    total_points: float
    questions: list[Question]
    grading_guidelines: list[str] = []