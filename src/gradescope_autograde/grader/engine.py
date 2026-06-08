from __future__ import annotations

from dataclasses import dataclass, field

from .providers.base import LLMProvider


@dataclass
class GradingResult:
    question_id: str
    score: float
    max_score: float
    feedback: str
    criteria_results: list[dict] = field(default_factory=list)


class GradingEngine:

    def __init__(self, provider: LLMProvider, temperature: float = 0.1) -> None:
        self.provider = provider
        self.temperature = temperature

    def grade(
        self,
        question: dict,
        student_answer: str,
        extra_instructions: str = "",
    ) -> dict:
        prompt = self._build_prompt(question, student_answer, extra_instructions)
        system_prompt = self._build_system_prompt()

        raw = self.provider.complete_structured(prompt, system_prompt=system_prompt)
        return self._parse_result(raw, question)

    def _build_system_prompt(self) -> str:
        return (
            "You are an expert grader evaluating student answers. "
            "You are precise, fair, and consistent.\n"
            "Always award partial credit when the student shows understanding "
            "but makes minor errors.\n"
            "Output ONLY valid JSON matching the requested schema."
        )

    def _build_prompt(
        self,
        question: dict,
        student_answer: str,
        extra_instructions: str,
    ) -> str:
        rubric_text = "\n".join(
            f"  - {criterion['name']}: {criterion['points']} pts — {criterion.get('description', '')}"
            for criterion in question.get("rubric", [])
        )
        instructions = (
            f"\n\nADDITIONAL GRADING INSTRUCTIONS:\n{extra_instructions}"
            if extra_instructions
            else ""
        )

        return (
            f"GRADING TASK\n\n"
            f"Question: {question['title']} ({question['max_points']} points max)\n"
            f"Type: {question.get('type', 'short_answer')}\n\n"
            f"RUBRIC:\n{rubric_text}\n{instructions}\n\n"
            f"STUDENT ANSWER:\n{student_answer}\n\n"
            f"Evaluate the student's answer against the rubric. Output JSON:\n"
            f"{{\n"
            f'  "score": <total points awarded>,\n'
            f'  "breakdown": [\n'
            f'    {{"criterion": "<criterion name>", "points_awarded": <points>, "max_points": <max>, "justification": "<why>"}}\n'
            f"  ],\n"
            f'  "confidence": <0.0-1.0, how confident you are in this grade>,\n'
            f'  "feedback": "<constructive, specific feedback for the student>",\n'
            f'  "flags": [<any concerns: "off_topic", "incomplete", "needs_review", "empty", "exceptional">]\n'
            f"}}"
        )

    def _parse_result(self, raw: dict, question: dict) -> dict:
        try:
            return {
                "question_id": question["id"],
                "score": float(raw["score"]),
                "breakdown": raw.get("breakdown", []),
                "confidence": float(raw.get("confidence", 0.5)),
                "feedback": raw.get("feedback", ""),
                "flags": raw.get("flags", []),
            }
        except (KeyError, ValueError, TypeError) as exc:
            return {
                "question_id": question["id"],
                "score": 0,
                "breakdown": [],
                "confidence": 0.0,
                "feedback": f"Error parsing grade result: {exc}",
                "flags": ["needs_review", "parse_error"],
            }
