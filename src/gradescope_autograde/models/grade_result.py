from datetime import datetime
from pydantic import BaseModel, Field

class CriterionResult(BaseModel):
    criterion: str
    points_awarded: float
    max_points: float
    justification: str = ""

class GradeResult(BaseModel):
    question_id: str
    score: float
    breakdown: list[CriterionResult] = []
    confidence: float = Field(ge=0.0, le=1.0)
    feedback: str = ""
    flags: list[str] = []
    model: str | None = None
    graded_at: datetime = Field(default_factory=datetime.now)