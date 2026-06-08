# Gradescope AutoGrade

AI-powered automated grading assistant for Gradescope. Built for TAs who want to reduce grading workload without sacrificing quality.

## Features

- **Fetch submissions** from Gradescope programmatically (HTTP scraping)
- **AI grading** with multiple LLM backends:
  - **OpenCode Go API** (default): deepseek-v4-flash for text, mimo-v2.5 for multimodal
  - **LM Studio** (local): gemma4, qwen3.5 — fully private, no data leaves your machine
  - OpenAI / Anthropic (optional)
- **Rubric-based evaluation** with structured JSON output
- **Human review queue** for low-confidence grades
- **PDF parsing** for reference questions/answers
- **Gradescope CSV export** for bulk upload
- **Progress tracking** with resume support

## Quick Start

```bash
# Install
pip install -e .

# Configure
cp config/config.example.yaml config/config.yaml
# Edit config.yaml with your credentials

# Authenticate
gs-autograde login --email your-email@university.edu

# List your courses
gs-autograde list courses

# List available AI models
gs-autograde models

# Grade an assignment
gs-autograde grade COURSE_ID ASSIGNMENT_ID --rubric config/rubrics/my_rubric.yaml

# Review flagged submissions
gs-autograde review

# Export results
gs-autograde export --format gradescope
```

## Architecture

```
CLI (Click + Rich)
    │
Workflow Pipeline (orchestrator)
    │
├── Gradescope Client (HTTP scraping)
│   └── Transport (session, auth, rate limiting)
│
└── Grading Engine
    ├── LLM Providers (OpenCode Go, LM Studio, OpenAI, Anthropic)
    ├── Rubric Parser (YAML)
    ├── PDF Parser (question/answer extraction)
    └── Review Queue (low-confidence flagging)
```

## LLM Providers

### OpenCode Go (Default)
```yaml
llm:
  provider: opencode-go
  model: deepseek-v4-flash          # Text grading (1M context)
  multimodal_model: mimo-v2.5       # For image/PDF submissions
```

### LM Studio (Local)
```yaml
llm:
  provider: lmstudio
  base_url: http://localhost:1234/v1
  auto_discover: true               # Auto-detect available models
```
Run `gs-autograde models` to see which local models are available.

## Rubric Format

```yaml
assignment: "Homework 1"
total_points: 100

questions:
  - id: "q1"
    title: "Explain recursion"
    max_points: 10
    type: short_answer
    rubric:
      - criterion: "Correct definition"
        points: 3
        description: "Mention function calling itself with base case"
      - criterion: "Example provided"
        points: 3
      - criterion: "Base case importance"
        points: 2
      - criterion: "Writing quality"
        points: 2

grading_guidelines:
  - "Award partial credit when student shows understanding"
  - "Blank answers → 0 points"
```

## Requirements

- Python 3.11+
- For PDF parsing: `pymupdf` (auto-installed)
- For LM Studio: [LM Studio](https://lmstudio.ai/) running locally

## License

GPL-3.0
