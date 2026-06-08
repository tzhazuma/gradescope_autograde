from pydantic import BaseModel
from .grade_result import GradeResult

class ReviewItem(BaseModel):
    submission_id: str
    question_id: str
    grade_result: GradeResult
    reason: str  # "low_confidence" | "flagged" | "error"
    status: str = "pending"  # "pending" | "approved" | "rejected"
    reviewer_notes: str | None = None