from pydantic import BaseModel

class PDFQuestion(BaseModel):
    question_number: int
    title: str = ""
    text: str
    reference_answer: str
    max_points: float = 10.0
    extra_instructions: str = ""