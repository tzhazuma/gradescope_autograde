from pydantic import BaseModel

class Course(BaseModel):
    id: str
    name: str
    short_name: str | None = None
    term: str | None = None
    role: str  # "instructor" | "student" | "ta"