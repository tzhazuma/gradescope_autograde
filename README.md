# Gradescope AutoGrade

[![Version](https://img.shields.io/badge/version-1.0.8-blue.svg)](https://github.com/tzhazuma/gradescope_autograde)
[![Python](https://img.shields.io/badge/python-3.11+-green.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-GPL--3.0-orange.svg)](LICENSE)

AI-powered automated grading assistant for Gradescope. Built for TAs who want to reduce grading workload without sacrificing quality.

**Repository**: https://github.com/tzhazuma/gradescope_autograde

📖 **Full User Manual**: [Download PDF](docs/manual.pdf)

## Features

- **AI-powered grading** — evaluate student answers against YAML rubrics using LLMs
- **Multiple LLM backends** — OpenCode Go (cloud), LM Studio (local/private)
- **Handles all submission types** — LaTeX PDFs, scanned handwriting (OCR), and photo/image uploads
- **PDF question parsing** — extract questions and reference answers from instructor PDFs
- **Rubric generation** — generate rubrics from question/answer PDFs using AI
- **Confidence-based review** — flags uncertain grades for human review
- **Interactive TUI** — terminal UI with course/assignment selection, model picker, live progress
- **Web GUI** — cross-platform browser interface with file upload and results export
- **Question selector** — fetch and select specific questions from Gradescope
- **LM Studio auto-management** — auto-detect, auto-start server, health checks
- **CSV/JSON export** — Gradescope-compatible bulk upload format
- **AI Chat Mode** — natural language assistant powered by OpenCode CLI

## Table of Contents

1. [Features](#features)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [Configuration](#configuration)
5. [CLI Commands](#cli-commands)
6. [LLM Providers](#llm-providers)
7. [Rubric Format](#rubric-format)
8. [PDF Question Parsing](#pdf-question-parsing)
9. [Workflow](#workflow)
10. [Architecture](#architecture)
11. [Changelog](#changelog)
12. [FAQ](#faq)

---

## Changelog

### v1.0.8 (2026-06-10)

**Security & Privacy Cleanup**

#### Fixes
- Removed generated rubric files from git (contained exam questions)
- Added `config/rubrics/generated_*.yaml` and `config/rubrics/hw*.yaml` to .gitignore
- Removed hardcoded course/assignment/question IDs from source code
- Replaced specific IDs with generic placeholders in examples

### v1.0.7 (2026-06-10)

**Submission Handling & Question Filtering Fixes**

#### Fixes
- Lowered empty submission threshold from 100 bytes to 10 bytes
- Added image submission detection and handling (non-PDF content)
- Fixed GS ID to rubric ID mapping (e.g., 71875707 → q4)
- When GS ID is entered, now correctly filters to only that question
- Improved error messages for empty/invalid submissions

### v1.0.6 (2026-06-10)

**Question ID Mapping Fix**

#### Fixes
- Fixed question ID mapping between GS questions (e.g., 71875707) and rubric questions (e.g., q4)
- When GS question ID is selected, grading now uses it for submission fetching
- When rubric question ID is entered (e.g., q1,q4), grading filters by rubric IDs

### v1.0.5 (2026-06-10)

**Image Submission Fix**

#### Fixes
- Fixed image-based submission handling by passing correct `gs_question_id`
- Removed hardcoded question ID `71029768` from TUI grading screen
- Added `gs_question_id` parameter to GradingScreen
- Config screen now passes fetched question ID to grading screen

### v1.0.4 (2026-06-10)

**Multimodal Grading Fix**

#### Fixes
- Fixed multimodal grading path to show score output after LLM call
- Added mimo-v2.5-pro to multimodal model detection in auto mode
- Added detailed error logging for multimodal LLM failures
- Added response length logging for debugging

### v1.0.3 (2026-06-10)

**Model Options & Navigation Fixes**

#### Fixes
- Added "Next: Grading Config →" button to TUI RubricScreen (Step 1)
- Added "Quit" button to TUI RubricScreen
- Added deepseek-v4-pro and mimo-v2.5-pro to TUI grading model selector fallback
- Added deepseek-v4-pro to GUI grading model selector

### v1.0.2 (2026-06-10)

**UI Improvements & Bug Fixes**

#### Improvements
- **TUI 2-Page Layout**: Split configuration into Step 1 (Rubric Setup) and Step 2 (Grading Config) for better usability
  - Step 1: Question PDF, rubric file, rubric generation
  - Step 2: Model selection, question selection, grading options
- **GUI Async Rubric Generation**: Run rubric generation in thread to prevent connection timeout
- **Chat Auto-Focus**: Chat input now auto-focuses on screen mount
- Removed 'q' binding from chat screen to allow typing 'q' in messages

#### Bug Fixes
- Fixed GUI "connection lost" error during rubric generation
- Fixed chat Enter key not working (removed conflicting 'q' binding)
- Added mimo-v2.5-pro model to GUI model selectors

### v1.0.1 (2026-06-10)

**Bug Fixes & Improvements**

#### Bug Fixes
- Fixed TUI config page layout - moved Fetch GS Questions button to proper position
- Fixed chat Enter key not sending message (separated event handlers)
- Added mimo-v2.5-pro model to GUI rubric and grading model selectors

#### Improvements
- Better TUI layout with question action buttons grouped together
- Consistent model options between TUI and GUI

### v1.0.0 (2026-06-10)

**Production Release** — All major features implemented and debugged.

#### New Features
- **Rubric Generation**: Generate rubrics from question/answer PDFs using AI
  - TUI: Added Generate Rubric button with model selector and output path display
  - GUI: Added Generate Rubric with answer PDF upload and model selection
- **Question Selector**: Fetch and select specific questions from Gradescope
  - TUI: Added dropdown selector that updates from GS questions or rubric
  - GUI: Added question selector dropdown with dynamic updates
- **AI Chat Mode**: Natural language assistant powered by OpenCode CLI
  - Added `--verbose` flag for detailed output
  - Fixed JSON streaming response handling

#### Bug Fixes
- Fixed macOS file picker (AppleScript syntax error)
- Fixed GUI upload handling (SpooledTemporaryFile → bytes conversion)
- Fixed ModelSelector widget ID conflict in TUI
- Fixed chat response timeout handling
- Improved error messages and user feedback

#### Improvements
- Increased chat timeout from 2 minutes to 2 minutes with proper timeout handling
- Added version badge and changelog to README
- Updated development status to Production/Stable

---

## Installation

### Requirements
- Python 3.11+ (Python 3.12 recommended)
- macOS (primary platform; Linux should also work)

### Setup

```bash
git clone https://github.com/tzhazuma/gradescope_autograde.git
cd gradescope_autograde
python3.12 -m venv venv
source venv/bin/activate
pip install -e .

# Optional: browser automation fallback
pip install -e ".[browser]"
playwright install chromium
```

### Verify

```bash
gs-autograde --help
```

Expected output:

```
Usage: gs-autograde [OPTIONS] COMMAND [ARGS]...

Commands:
  export     Export results to CSV/JSON
  grade      Run full grading pipeline
  gui        Launch web GUI
  list       List Gradescope resources
  login      Authenticate with Gradescope
  models     List available AI models
  parse-pdf  Extract questions from reference PDF
  review     Interactive review of flagged grades
  tui        Launch interactive terminal UI
  upload     Submit grades to Gradescope
```

---

## Quick Start

### Step 1: Configure

```bash
cp config/config.example.yaml config/config.yaml
```

Edit `config/config.yaml`:

```yaml
auth:
  email: "your-email@university.edu"
  password: "your-password"

llm:
  provider: "opencode-go"        # Use OpenCode Go API
  model: "deepseek-v4-flash"     # Fast text grading
```

Set your API key:

```bash
export OPENCODE_GO_API_KEY="your-api-key"
```

### Step 2: Login

```bash
gs-autograde login
```

### Step 3: Explore

```bash
gs-autograde list courses
gs-autograde list assignments 123456
gs-autograde models          # See available AI models
```

### Step 4: Create a Rubric

```bash
# From a question/answer PDF
gs-autograde parse-pdf questions.pdf -o config/rubrics/my_rubric.yaml

# Or create manually (see Rubric Format section)
vim config/rubrics/my_rubric.yaml
```

### Alternative: Interactive TUI

```bash
gs-autograde tui
```

### Alternative: Web GUI

```bash
gs-autograde gui
```

### Step 5: Grade (Dry Run First!)

```bash
gs-autograde grade 123456 789012 \
  --rubric config/rubrics/my_rubric.yaml \
  --dry-run
```

### Step 6: Review Flagged Grades

```bash
gs-autograde review
```

### Step 7: Grade for Real

```bash
gs-autograde grade 123456 789012 --rubric config/rubrics/my_rubric.yaml
```

### Step 8: Export

```bash
gs-autograde export --format gradescope   # For Gradescope bulk upload
gs-autograde export --format detailed     # Per-criterion breakdown
gs-autograde export --format json         # Full JSON
```

---

## Configuration

Full `config/config.yaml` reference:

```yaml
auth:
  email: "your-email@university.edu"
  password: ""
  cookie: ""                          # Browser session cookie (alternative)

gradescope:
  base_url: "https://www.gradescope.com"
  request_delay: 1.0                  # Seconds between requests
  max_retries: 3

llm:
  provider: "opencode-go"             # opencode-go | lmstudio
  model: "deepseek-v4-flash"          # Text grading (1M context)
  multimodal_model: "mimo-v2.5"       # For image/PDF submissions
  api_key: "${OPENCODE_GO_API_KEY}"   # Reads from environment
  base_url: "https://opencode.ai/zen/go/v1"
  temperature: 0.1                    # Low = consistent grading
  max_tokens: 4096

lmstudio:
  base_url: "http://localhost:1234/v1"
  auto_discover: true                 # Auto-detect available models

workflow:
  auto_upload: false                  # Auto-upload after grading
  review_threshold: 0.7               # Confidence < 0.7 → flag for review
  batch_size: 50

output:
  grades_dir: "data/output/grades/"
  format: "gradescope_csv"
  generate_feedback: true
```

---

## CLI Commands

### `login` — Authenticate

```bash
gs-autograde login                          # Interactive
gs-autograde login --email user@univ.edu    # Email-based
gs-autograde login --cookie "session=..."   # Cookie from browser DevTools
gs-autograde login --browser                # Browser-based (auto-capture cookies)
```

### `list` — Browse Gradescope

```bash
gs-autograde list courses
gs-autograde list assignments <COURSE_ID>
gs-autograde list submissions <COURSE_ID> <ASSIGNMENT_ID>
```

### `models` — AI Model Discovery

```bash
gs-autograde models
```

Shows a Rich table of available models from all providers. For LM Studio, queries `GET /api/v1/models` in real-time.

### `tui` — Interactive Terminal UI

```bash
gs-autograde tui
```

Launches a full-screen Textual-based terminal interface with:
- **Course selection** — browse and select from your Gradescope courses
- **Assignment selection** — pick the assignment to grade
- **Configuration** — choose question PDF, rubric YAML, model, and grading instructions
- **Rubric generation** — generate rubrics from question/answer PDFs using AI
- **Question selector** — fetch and select specific questions from Gradescope
- **Live grading** — watch progress with a progress bar and log output
- **Results review** — view scores with confidence levels and flags
- **AI Chat** — integrated chat interface for natural language commands

Keyboard navigation: `Tab` to move focus, `Space` to toggle selection, `Enter` to activate,
`Escape` to go back, `q` to quit. Selected items appear in **bold**, unchecked items in dim.

### `gui` — Web GUI

```bash
gs-autograde gui                          # Open at http://127.0.0.1:8080
gs-autograde gui --port 3000              # Custom port
gs-autograde --config my-config.yaml gui  # Custom config path
```

Launches a cross-platform web interface (NiceGUI) that opens in your browser. Features:
- **5-step wizard**: Login → Select Assignment → Configure → Grade → Export
- **File upload**: Drag & drop question PDFs and rubric YAML files (auto-parses YAML rubrics)
- **Provider selection**: Choose between OpenCode Go (cloud) and LM Studio (local)
- **Extra instructions**: Add per-assignment grading notes (injected into rubric)
- **Live progress**: Real-time grading progress with log output
- **Results table**: View scores, export to Gradescope CSV / Detailed CSV / JSON

### LM Studio Auto-Management

The LM Studio provider now supports automatic server lifecycle management:

```python
from gradescope_autograde.lmstudio.manager import LmsManager

with LmsManager() as lm:
    lm.ensure_running()  # Auto-starts the server if not running
    # ... use LM Studio for grading ...
# Server stops automatically when done (if it was started by us)
```

The manager also provides detection and install guidance:

```python
from gradescope_autograde.lmstudio.manager import detect_lmstudio, get_install_instructions

status = detect_lmstudio()
print(f"LM Studio installed: {status['installed']}")
print(f"Server running: {status['server_running']}")

if not status['installed']:
    print(get_install_instructions())
```

This is automatically used by the TUI and GUI — no manual server start needed.

### `parse-pdf` — Extract Questions

```bash
gs-autograde parse-pdf questions.pdf                    # Display extracted questions
gs-autograde parse-pdf questions.pdf -o rubric.yaml     # Save as rubric template
gs-autograde parse-pdf questions.pdf --separator "## Q" # Custom separator
```

### `grade` — Run Grading Pipeline

```bash
# Dry run (grade locally, don't upload)
gs-autograde grade COURSE_ID ASSIGN_ID -r rubric.yaml --dry-run

# Upload grades to Gradescope
gs-autograde grade COURSE_ID ASSIGN_ID -r rubric.yaml --upload

# Grade specific questions only (from rubric IDs)
gs-autograde grade COURSE_ID ASSIGN_ID -r rubric.yaml --questions q1,q4

# Multimodal grading (handwritten PDFs → images → LLM)
gs-autograde grade COURSE_ID ASSIGN_ID -r rubric.yaml --model mimo-v2.5 --extraction multimodal

# Generate rubric on-the-fly from question/answer PDFs
gs-autograde grade COURSE_ID ASSIGN_ID -r answer.pdf --gen-rubric --rubric-gen-model deepseek-v4-pro

# Full run with details
gs-autograde grade COURSE_ID ASSIGN_ID -r rubric.yaml --upload --verbose
```

> ⚠️ **Upload safety**: Only submissions with error flags (`pipeline_error`, `extraction_error`) are skipped. Submissions with valid content but score=0 are uploaded normally.

### `review` — Review Flagged Grades

```bash
gs-autograde review
```

Interactive: shows each flagged submission with student name, AI score, confidence, and feedback. Options: approve, reject (with notes), skip.

### `upload` — Submit Grades

```bash
gs-autograde upload COURSE_ID ASSIGN_ID --results results.json
```

> **Note**: For assignments with individual questions, the `--upload` flag on `grade` posts grades directly. For single-score assignments, use the CSV export workflow:
> ```bash
> gs-autograde grade ... --questions q4 --dry-run  # grade first
> gs-autograde export -r results.json --format gradescope  # export CSV
> # Then import the CSV manually on Gradescope: Assignments → Review Grades → Import Scores
> ```
> Uploads automatically skip submissions with error flags.

### `export` — Export Results

```bash
gs-autograde export --format gradescope     # Gradescope bulk upload CSV
gs-autograde export --format detailed       # Per-criterion breakdown CSV
gs-autograde export --format json           # Full JSON export
```

### `chat` — AI Chat Mode

```bash
gs-autograde chat                              # Interactive REPL
gs-autograde chat "grade hw9 q4 for si120"     # Single-shot command
gs-autograde chat -p lmstudio -m gemma4-12b    # Use LM Studio
gs-autograde chat -v "what is 2+2?"            # Verbose output
```

Natural language assistant powered by OpenCode CLI. Ask questions about grading, request rubric generation, or execute grading commands using natural language.

---

## LLM Providers

### OpenCode Go (Default, Cloud)

```yaml
llm:
  provider: "opencode-go"
  model: "deepseek-v4-flash"         # 284B/13B, 1M context, text-only
  multimodal_model: "mimo-v2.5"      # 310B/15B, 1M context, text+image+video
```

### LM Studio (Local, Private)

```yaml
llm:
  provider: "lmstudio"
lmstudio:
  auto_discover: true
  base_url: "http://localhost:1234/v1"
```

1. Install [LM Studio](https://lmstudio.ai/)
2. Download models (gemma4, qwen3.5)
3. Start local server on port 1234
4. Run `gs-autograde models` to verify

**Recommended local models:**

| Model | Size | Context | Best For |
|-------|------|---------|----------|
| Gemma 4 12B | 12B | 131K | Balanced grading |
| Qwen 3.5 9B | 9B | 262K | Code/math grading |
| Gemma 4 E4B | 4.5B | 131K | Quick checks |
| Qwen 3.5 4B | 4B | 262K | Lightweight |

> ⚠️ **Privacy**: Cloud providers receive student answers. LM Studio keeps everything on your machine.

---

## Rubric Format

Rubrics are YAML files defining how the AI evaluates student answers.

```yaml
assignment: "Homework 1: Recursion"
total_points: 100

questions:
  - id: "q1"
    title: "Define recursion"
    max_points: 10
    type: short_answer
    rubric:
      - criterion: "Correct definition"
        points: 3
        description: "Must mention a function calling itself"
      - criterion: "Base case mentioned"
        points: 3
      - criterion: "Example provided"
        points: 2
      - criterion: "Clarity"
        points: 2

  - id: "q2"
    title: "Analyze time complexity"
    max_points: 15
    extra_instructions: "Accept both O(n log n) and O(n²) if justified"
    rubric:
      - criterion: "Correct big-O"
        points: 5
      - criterion: "Explanation"
        points: 5
      - criterion: "Edge cases"
        points: 5

grading_guidelines:
  - "Award partial credit when student shows understanding"
  - "Blank answers → 0 points, flag for review"
  - "Off-topic answers → 0 points, flag for review"
```

### Best Practices

1. **Be specific** — vague criteria produce inconsistent grades
2. **Use checklist-style** — research shows checklist rubrics outperform holistic ones
3. **Include point values** per criterion
4. **Add descriptions** telling the AI what to look for
5. **Use `extra_instructions`** for edge cases and exceptions
6. **Always test with `--dry-run`** first

---

## PDF Question Parsing

If you have a PDF with questions and reference answers:

```
## Question 1
What is the time complexity of quicksort?

Answer: O(n log n) average case, O(n²) worst case.

## Question 2
Explain the difference between BFS and DFS.

Answer: BFS uses a queue, DFS uses a stack...
```

```bash
gs-autograde parse-pdf exam_questions.pdf -o rubric.yaml
```

Edit the generated YAML to add rubric criteria and point values.

---

## Workflow

```
┌─────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Login  │ →  │  Fetch   │ →  │  Grade   │ →  │  Upload  │
│  GS     │    │  Subms   │    │  (LLM)   │    │  Scores  │
└─────────┘    └──────────┘    └──────────┘    └──────────┘
                                    │
                               ┌────┴────┐
                               │ Review  │ (confidence < 70%)
                               │ Queue   │
                               └─────────┘
```

**Resume support**: If grading is interrupted, re-run the same command. The progress tracker skips already-processed submissions. Delete `.grading_state.json` to force a full regrade.

**Output files**:
```
data/output/grades/
├── results.json             # Full results with breakdowns
├── gradescope_upload.csv    # For manual Gradescope upload
├── detailed_report.csv      # Per-criterion breakdown
└── review_queue.json        # Flagged submissions
```

---

## Architecture

```
CLI (Click + Rich)
    │
Workflow Pipeline
    │
├── Gradescope Client (HTTP scraping)
│   ├── Transport (CSRF auth, cookies, rate limiting)
│   ├── HTML Parser
│   └── Browser Fallback (Playwright)
│
├── Grading Engine
│   ├── LLM Providers (OpenCodeGo, LMStudio, OpenAI, Anthropic)
│   ├── Rubric Parser (YAML)
│   ├── PDF Parser (pymupdf)
│   └── Review Queue (confidence threshold)
│
├── LM Studio Manager (auto-detect, start/stop, health checks)
├── Textual TUI (interactive terminal UI)
└── NiceGUI Web GUI (cross-platform web interface)
```

---

## FAQ

**Does this work with any Gradescope course?**
Yes, as long as you have instructor or TA access.

**Is my data private?**
Cloud providers receive student answers. LM Studio keeps everything on your machine.

**How accurate is AI grading?**
LLMs match human accuracy on structured, rubric-based tasks. Always spot-check and use the review queue.

**What if Gradescope changes their HTML?**
The HTML parser is isolated in `client/parser.py`. The browser fallback provides an alternative path.

**Can I grade multiple assignments at once?**
Run separate terminals for different assignments. Each has its own progress state.

**How do I regrade?**
Delete `.grading_state.json` and re-run. Or edit your rubric and re-grade only flagged submissions.

---

## License

GPL-3.0 — See [LICENSE](LICENSE)
