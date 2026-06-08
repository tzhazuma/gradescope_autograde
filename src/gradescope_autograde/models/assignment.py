from datetime import datetime
from pydantic import BaseModel

class Assignment(BaseModel):
    id: str
    course_id: str
    title: str
    due_date: datetime | None = None
    points: float | None = None
    submission_type: str = "pdf"  # "pdf" | "code" | "text" | "online"
    num_submissions: int = 0