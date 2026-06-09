"""LaTeX rubric parser — extracts questions and reference answers from .tex files."""

from __future__ import annotations

import re
from pathlib import Path


def extract_text_from_tex(path: str) -> str:
    """Read and strip LaTeX comments from a .tex file."""
    raw = Path(path).read_text(encoding="utf-8")

    lines = []
    for line in raw.split("\n"):
        stripped = line.split("%", 1)[0] if not re.match(r".*[{\\$]", line) else line
        lines.append(stripped)
    return "\n".join(lines)


def _clean_latex(text: str) -> str:
    """Strip LaTeX commands and braces, keeping readable text."""
    text = re.sub(r"\\[a-zA-Z]+\{.*?\}", "", text)
    text = text.replace("{", "").replace("}", "")
    text = re.sub(r"\\(?:textbf|textit|texttt|emph|underline)\s*", "", text)
    text = re.sub(r"\$\$.+?\$\$", "", text, flags=re.DOTALL)
    text = re.sub(r"\$.+?\$", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_tex_questions(
    text: str,
    default_points: float = 10.0,
) -> list[dict]:
    """Extract questions and reference answers from LaTeX content.

    Supports multiple LaTeX question formats:
    - ``\\section{Question N}`` / ``\\subsection{Question N}``
    - ``\\question`` (exam class)
    - ``\\item`` inside ``enumerate`` whose parent has ``question`` in its label

    Each section's text before the next question or an ``Answer:`` /
    ``\\textbf{Answer:}`` marker is treated as the question text; content
    after the answer marker is the reference answer.
    """
    questions: list[dict] = []
    seen_texts: set[str] = set()

    # Split on section-like boundaries: \section, \subsection, \question, or
    # an \item whose preceding text matches a question pattern.
    section_pattern = re.compile(
        r"(?:(?:\\section|\\subsection|\\subsubsection)\*?\s*\{([^}]+)\})"
        r"|(?:\\question\s*(.*?)(?=\\question|\\end|$))"
        r"|(?:\\item\s+(.*?)(?=\\item|\\end|$))",
        re.DOTALL | re.IGNORECASE,
    )

    # Strategy: find all section/question boundaries first
    parts = list(section_pattern.finditer(text))
    if not parts:
        # Fallback: treat \n\n as question separator
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        parts = []
        for i, p in enumerate(paragraphs):
            # Try to auto-detect question boundaries
            if re.match(r"(?i)question\s+\d+|q\d+[.)]|(\d+)[.)]", p):
                parts.append(p)

    for i, match in enumerate(parts):
        title_raw = match.group(1) or match.group(2) or match.group(3) or ""
        title = _clean_latex(title_raw).strip()

        # Determine the content boundaries
        start = match.end()
        if i + 1 < len(parts):
            end = parts[i + 1].start()
        else:
            end = len(text)

        content_block = text[start:end].strip()

        # Split question text and answer
        answer_markers = [
            r"\\textbf\s*\{\s*Answer\s*:?\s*\}",
            r"\\textit\s*\{\s*Answer\s*:?\s*\}",
            r"(?i)^Answer\s*:",
            r"(?i)^Answer\s*\n",
            r"(?i)^\\textbf\{Answer\}",
            r"\\boxed\s*\{",
        ]
        answer_split_pos = len(content_block)
        for marker in answer_markers:
            m = re.search(marker, content_block, re.MULTILINE)
            if m:
                answer_split_pos = min(answer_split_pos, m.start())

        question_text = _clean_latex(content_block[:answer_split_pos].strip())
        answer_text = _clean_latex(content_block[answer_split_pos:].strip())

        # Skip empty or duplicate questions
        dedup_key = f"{question_text[:80]}"
        if not question_text or dedup_key in seen_texts:
            continue
        seen_texts.add(dedup_key)

        questions.append({
            "question_number": len(questions) + 1,
            "title": title or f"Question {len(questions) + 1}",
            "text": question_text,
            "reference_answer": answer_text,
            "max_points": default_points,
        })

    # If no structured questions found, treat the whole document as one
    if not questions and text.strip():
        questions.append({
            "question_number": 1,
            "title": "Question 1",
            "text": _clean_latex(text),
            "reference_answer": "",
            "max_points": default_points,
        })

    return questions


def parse_reference_tex(path: str) -> list[dict]:
    """Parse a .tex file and extract questions with reference answers.

    Returns the same dict format as :func:`parse_reference_pdf`
    so callers can use them interchangeably.
    """
    raw_text = extract_text_from_tex(path)
    return parse_tex_questions(raw_text)
