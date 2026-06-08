from __future__ import annotations

import pymupdf


def extract_text_from_pdf(path: str) -> list[dict]:
    doc = pymupdf.open(path)
    pages: list[dict] = []
    for i, page in enumerate(doc):
        text = page.get_text()
        if text.strip():
            pages.append({"page_num": i + 1, "text": text.strip()})
    doc.close()
    return pages


def split_into_questions(
    pages: list[dict],
    separator: str = "## Question",
) -> list[dict]:
    questions: list[dict] = []
    current_text: list[str] = []
    current_num = 1

    for page in pages:
        text = page["text"]
        parts = text.split(separator)

        for i, part in enumerate(parts):
            if i == 0 and current_text:
                current_text.append(part)
            elif i == 0:
                current_text.append(part)
            else:
                if current_text:
                    questions.append(
                        {
                            "question_number": current_num,
                            "text": "\n".join(current_text).strip(),
                        }
                    )
                    current_num += 1
                current_text = [separator + part]

    if current_text:
        questions.append(
            {
                "question_number": current_num,
                "text": "\n".join(current_text).strip(),
            }
        )

    return questions


def parse_reference_pdf(
    path: str,
    points_map: dict[int, float] | None = None,
    extra_instructions: dict[int, str] | None = None,
) -> list[dict]:
    pages = extract_text_from_pdf(path)
    raw_questions = split_into_questions(pages)

    parsed: list[dict] = []
    for q in raw_questions:
        num = q["question_number"]
        text = q["text"]

        parts = text.split("\n\n", 1)
        question_text = parts[0]
        answer_text = parts[1] if len(parts) > 1 else ""

        parsed.append(
            {
                "question_number": num,
                "text": question_text.strip(),
                "reference_answer": answer_text.strip(),
                "max_points": points_map.get(num, 10.0) if points_map else 10.0,
                "extra_instructions": (
                    extra_instructions.get(num, "") if extra_instructions else ""
                ),
            }
        )

    return parsed
