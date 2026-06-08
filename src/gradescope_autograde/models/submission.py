from datetime import datetime
from pydantic import BaseModel

class Submission(BaseModel):
    id: str
    assignment_id: str
    student_name: str
    student_email: str | None = None
    submitted_at: datetime | None = None
    graded: bool = False
    score: float | None = None
    max_score: float | None = None