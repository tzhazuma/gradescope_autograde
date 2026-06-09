"""LLM-based rubric generation from reference question/answer PDFs."""

from __future__ import annotations

from pathlib import Path


def generate_rubric(
    question_pdf: str,
    answer_pdf: str | None = None,
    extra_instructions: str = "",
    model: str = "deepseek-v4-flash",
    api_key: str | None = None,
    provider_type: str = "opencode-go",
    lmstudio_model: str | None = None,
) -> dict:
    """Use an LLM to generate a grading rubric from reference materials.

    Args:
        question_pdf: Path to the question PDF.
        answer_pdf: Optional path to the answer/solution PDF.
        extra_instructions: Additional grading instructions.
        model: OpenCode Go model ID for rubric generation.
        api_key: OpenCode Go API key.
        provider_type: ``"opencode-go"`` or ``"lmstudio"``.
        lmstudio_model: LM Studio model name (when provider is lmstudio).

    Returns:
        A rubric dict with a ``questions`` list, ready for use by
        :func:`~gradescope_autograde.workflow.pipeline.Pipeline.run`.
    """
    if provider_type == "lmstudio":
        from .providers.lmstudio import LMStudioProvider
        provider = LMStudioProvider(model=lmstudio_model)
    else:
        from .providers.opencode_go import OpenCodeGoProvider
        provider = OpenCodeGoProvider(model=model, api_key=api_key)

    # Read the question PDF text
    import pymupdf
    q_doc = pymupdf.open(question_pdf)
    q_text = "\n".join(page.get_text() for page in q_doc)
    q_doc.close()

    # Read the answer PDF text
    a_text = ""
    if answer_pdf and Path(answer_pdf).exists():
        a_doc = pymupdf.open(answer_pdf)
        a_text = "\n".join(page.get_text() for page in a_doc)
        a_doc.close()

    prompt = (
        "You are a teaching assistant creating a grading rubric. "
        "Given the following question and reference answer, create a detailed "
        "grading rubric in JSON format.\n\n"
    )
    if q_text.strip():
        prompt += f"QUESTION:\n{q_text[:8000]}\n\n"
    if a_text.strip():
        prompt += f"REFERENCE ANSWER:\n{a_text[:8000]}\n\n"
    if extra_instructions:
        prompt += f"ADDITIONAL INSTRUCTIONS:\n{extra_instructions}\n\n"

    prompt += (
        "Output ONLY valid JSON matching this EXACT schema:\n"
        '{"questions": [{"id": "q1", "title": "Question 1", '
        '"max_points": 10, "type": "short_answer", '
        '"rubric": [{"name": "criterion name", "points": 5, '
        '"description": "what to look for"}]}]}\n\n'
        "Distribute total points across criteria. "
        "Each question should have 2-5 criteria with clear point values."
    )

    raw = provider.complete(
        prompt=prompt,
        response_format="json",
    )
    import json
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {"questions": []}

    if not result.get("questions"):
        result = {
            "questions": [{
                "id": "q1",
                "title": "Question 1",
                "max_points": 10,
                "type": "short_answer",
                "rubric": [{"name": "correctness", "points": 10, "description": "Correct answer"}],
            }]
        }
    return result
