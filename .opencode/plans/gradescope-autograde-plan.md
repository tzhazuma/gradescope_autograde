# Gradescope AutoGrade — Implementation Plan

> **Status**: Ready for execution
> **Created**: 2026-06-08
> **Strategy**: TDD · Atomic commits · Parallel waves
> **Total tasks**: 38 across 6 waves

---

## Architecture Overview

```
┌──────────────────────────────────────────────────┐
│         CLI / Workflow Orchestrator               │  Wave 4
├──────────────────────────────────────────────────┤
│            Grading Engine (LLM)                   │  Wave 2
├──────────────────────────────────────────────────┤
│         Gradescope Client (HTTP)                  │  Wave 1
├──────────────────────────────────────────────────┤
│     Transport (Session / Auth / Rate Limit)       │  Wave 0 (fix existing)
├──────────────────────────────────────────────────┤
│     Domain Models (Pydantic)                      │  Wave 0 (new)
└──────────────────────────────────────────────────┘
```

---

## Wave 0: Foundation & Domain Models

**Goal**: Pydantic models, config loader, test infrastructure, fix GSSession auth.
**Dependencies**: None (start here).
**Parallelizable**: Yes — all tasks within this wave are independent after 0.1.

### Tasks

| ID | Task | File(s) | Commit | Category | Deps |
|----|------|---------|--------|----------|------|
| 0.1 | Pydantic domain models | `src/gradescope_autograde/models/__init__.py`, `course.py`, `assignment.py`, `submission.py` | `feat(models): add core domain models` | `quick` | — |
| 0.2 | Grading domain models | `src/gradescope_autograde/models/rubric.py`, `grade_result.py`, `review.py` | `feat(models): add grading domain models` | `quick` | 0.1 |
| 0.3 | Config loader | `src/gradescope_autograde/config.py` | `feat(config): add YAML config loader` | `quick` | 0.1 |
| 0.4 | Test infrastructure | `tests/conftest.py`, `tests/fixtures/` | `test: add test infrastructure and fixtures` | `quick` | — |
| 0.5 | Fix GSSession CSRF auth | `src/gradescope_autograde/transport/session.py` | `fix(transport): add CSRF token scraping to login` | `quick` | 0.4 |
| 0.6 | GSSession tests | `tests/unit/test_session.py` | `test(transport): add session auth tests` | `quick` | 0.5 |

### Models to implement

```python
# course.py
class Course(BaseModel):
    id: str
    name: str
    short_name: str | None = None
    term: str | None = None
    role: str  # "instructor" | "student"

# assignment.py
class Assignment(BaseModel):
    id: str
    course_id: str
    title: str
    due_date: datetime | None = None
    points: float | None = None
    submission_type: str  # "pdf" | "code" | "text"
    num_submissions: int = 0

# submission.py
class Submission(BaseModel):
    id: str
    assignment_id: str
    student_id: str
    student_name: str | None = None
    status: str  # "submitted" | "graded" | "missing"
    score: float | None = None
    submitted_at: datetime | None = None
    content_path: Path | None = None  # local cache

# rubric.py
class RubricCriterion(BaseModel):
    criterion: str
    points: float
    description: str | None = None

class QuestionRubric(BaseModel):
    id: str
    title: str
    max_points: float
    type: str  # "short_answer" | "essay" | "code" | "multiple_choice"
    rubric: list[RubricCriterion]

class GradingRubric(BaseModel):
    assignment: str
    total_points: float
    questions: list[QuestionRubric]
    grading_guidelines: list[str] = []

# grade_result.py
class CriterionResult(BaseModel):
    criterion: str
    points_awarded: float
    max_points: float
    justification: str

class GradeResult(BaseModel):
    question_id: str
    score: float
    breakdown: list[CriterionResult]
    confidence: float  # 0.0-1.0
    feedback: str
    flags: list[str] = []
    model: str | None = None
    graded_at: datetime = Field(default_factory=datetime.now)

# review.py
class ReviewItem(BaseModel):
    submission_id: str
    question_id: str
    grade_result: GradeResult
    reason: str  # "low_confidence" | "flagged" | "error"
    status: str = "pending"  # "pending" | "approved" | "rejected"
    reviewer_notes: str | None = None
```

### GSSession Fix

The current `login()` method POSTs directly without scraping the CSRF token. Fix:

```python
def login(self, email: str, password: str) -> bool:
    # Step 1: GET login page, scrape authenticity_token
    resp = self._session.get(f"{self.base_url}/login")
    soup = BeautifulSoup(resp.text, "html.parser")
    token_tag = soup.find("input", {"name": "authenticity_token"})
    if not token_tag:
        raise AuthenticationError("Could not find CSRF token")
    csrf_token = token_tag["value"]

    # Step 2: POST with token
    response = self._session.post(
        f"{self.base_url}/login",
        data={
            "session[email]": email,
            "session[password]": password,
            "authenticity_token": csrf_token,
        },
        allow_redirects=False,
    )
    self._authenticated = response.status_code == 302
    return self._authenticated
```

### Success Criteria
- [ ] All Pydantic models pass validation tests
- [ ] Config loader reads YAML and returns typed config
- [ ] GSSession login scrapes CSRF token and authenticates
- [ ] Cookie save/load round-trips correctly
- [ ] `ruff check` and `mypy` pass

---

## Wave 1: Gradescope Client

**Goal**: Full HTTP client for course/assignment/submission CRUD.
**Dependencies**: Wave 0 complete.
**Parallelizable**: YES — runs in parallel with Wave 2 (Grading Engine).

### Tasks

| ID | Task | File(s) | Commit | Category | Deps |
|----|------|---------|--------|----------|------|
| 1.1 | Client base + list_courses | `src/gradescope_autograde/client/__init__.py`, `client.py` | `feat(client): add GSClient with list_courses` | `business-logic` | 0.6 |
| 1.2 | Client tests | `tests/unit/test_client.py` | `test(client): add client course listing tests` | `quick` | 1.1 |
| 1.3 | list_assignments | `src/gradescope_autograde/client/client.py` | `feat(client): add list_assignments` | `quick` | 1.1 |
| 1.4 | list_submissions | `src/gradescope_autograde/client/client.py` | `feat(client): add list_submissions` | `quick` | 1.3 |
| 1.5 | get_submission_content | `src/gradescope_autograde/client/client.py` | `feat(client): add submission content fetcher` | `business-logic` | 1.4 |
| 1.6 | upload_grade | `src/gradescope_autograde/client/client.py` | `feat(client): add grade upload` | `quick` | 1.4 |
| 1.7 | Full client tests | `tests/unit/test_client.py` | `test(client): add full client CRUD tests` | `quick` | 1.6 |
| 1.8 | Rate limiter mixin | `src/gradescope_autograde/client/rate_limiter.py` | `feat(client): add rate limiter with backoff` | `quick` | 1.1 |

### GSClient Design

```python
class GSClient:
    def __init__(self, session: GSSession):
        self._session = session

    def list_courses(self) -> list[Course]:
        """GET /api/v1/courses -> parse HTML table -> list[Course]"""

    def list_assignments(self, course_id: str) -> list[Assignment]:
        """GET /courses/{id} -> parse assignments table"""

    def list_submissions(self, course_id: str, assignment_id: str) -> list[Submission]:
        """GET /courses/{cid}/assignments/{aid}/submissions -> parse table"""

    def get_submission_content(self, course_id: str, assignment_id: str, submission_id: str) -> str:
        """GET submission PDF/text -> extract text content"""

    def upload_grade(self, course_id: str, assignment_id: str, submission_id: str,
                     score: float, feedback: str = "") -> bool:
        """POST grade to Gradescope"""
```

### Gradescope HTML Parsing Strategy

Gradescope serves most data as **HTML tables** (not JSON API). Use BeautifulSoup to parse:

```python
def _parse_courses_table(self, html: str) -> list[Course]:
    soup = BeautifulSoup(html, "html.parser")
    courses = []
    for row in soup.select("table.courseList tr"):
        link = row.select_one("a[href*='/courses/']")
        if link:
            course_id = link["href"].split("/courses/")[-1]
            courses.append(Course(id=course_id, name=link.text.strip(), ...))
    return courses
```

### Success Criteria
- [ ] `list_courses()` returns typed Course objects from HTML
- [ ] `list_assignments()` returns typed Assignment objects
- [ ] `list_submissions()` returns typed Submission objects
- [ ] `upload_grade()` posts score and returns success/failure
- [ ] Rate limiter enforces delay between requests
- [ ] All tests pass with mocked HTTP responses

---

## Wave 2: Grading Engine

**Goal**: LLM-powered grading with structured output, rubric parsing, review queue.
**Dependencies**: Wave 0 complete.
**Parallelizable**: YES — runs in parallel with Wave 1.

### Tasks

| ID | Task | File(s) | Commit | Category | Deps |
|----|------|---------|--------|----------|------|
| 2.1 | Rubric parser | `src/gradescope_autograde/grader/rubric_parser.py` | `feat(grader): add YAML rubric parser` | `quick` | 0.2 |
| 2.2 | Rubric parser tests | `tests/unit/test_rubric_parser.py` | `test(grader): add rubric parser tests` | `quick` | 2.1 |
| 2.3 | LLM provider abstraction | `src/gradescope_autograde/grader/llm_provider.py` | `feat(grader): add LLM provider abstraction` | `business-logic` | 0.2 |
| 2.4 | OpenAI provider | `src/gradescope_autograde/grader/providers/openai.py` | `feat(grader): add OpenAI provider` | `business-logic` | 2.3 |
| 2.5 | Anthropic provider | `src/gradescope_autograde/grader/providers/anthropic.py` | `feat(grader): add Anthropic provider` | `business-logic` | 2.3 |
| 2.6 | Ollama provider | `src/gradescope_autograde/grader/providers/ollama.py` | `feat(grader): add Ollama provider` | `business-logic` | 2.3 |
| 2.7 | Prompt builder | `src/gradescope_autograde/grader/prompt_builder.py` | `feat(grader): add structured prompt builder` | `quick` | 2.1 |
| 2.8 | Output parser | `src/gradescope_autograde/grader/output_parser.py` | `feat(grader): add structured JSON output parser` | `quick` | 2.7 |
| 2.9 | Grading engine | `src/gradescope_autograde/grader/engine.py` | `feat(grader): add grading engine orchestrator` | `business-logic` | 2.4, 2.8 |
| 2.10 | Review queue | `src/gradescope_autograde/grader/review_queue.py` | `feat(grader): add review queue for low-confidence` | `quick` | 2.9 |
| 2.11 | Grader tests | `tests/unit/test_grader.py` | `test(grader): add grading engine tests` | `quick` | 2.10 |
| 2.12 | Provider tests | `tests/unit/test_providers.py` | `test(grader): add LLM provider tests` | `quick` | 2.6 |

### LLM Provider Abstraction

```python
from abc import ABC, abstractmethod

class LLMProvider(ABC):
    @abstractmethod
    async def grade(self, prompt: str, schema: dict) -> dict:
        """Send prompt, return structured JSON matching schema."""
        ...

    @abstractmethod
    def name(self) -> str: ...

class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o", temperature: float = 0.1):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.temperature = temperature

    async def grade(self, prompt: str, schema: dict) -> dict:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)
```

### Prompt Template

```python
GRADING_PROMPT = """You are a grading assistant for {course_name} - {assignment_name}.

## Question
{question_text}

## Rubric
{rubric_json}

## Student Answer
{student_answer}

## Grading Guidelines
{guidelines}

Evaluate the student's answer against each rubric criterion. Return ONLY valid JSON:
{{
  "question_id": "{question_id}",
  "score": <total_points_awarded>,
  "breakdown": [
    {{
      "criterion": "<criterion name>",
      "points_awarded": <points>,
      "max_points": <max>,
      "justification": "<brief explanation>"
    }}
  ],
  "confidence": <0.0-1.0>,
  "feedback": "<constructive feedback for the student>",
  "flags": ["<any concerns: off_topic, incomplete, needs_review>"]
}}
"""
```

### Review Queue Logic

```python
class ReviewQueue:
    def __init__(self, threshold: float = 0.7):
        self.threshold = threshold
        self._items: list[ReviewItem] = []

    def check(self, submission_id: str, result: GradeResult) -> ReviewItem | None:
        if result.confidence < self.threshold:
            item = ReviewItem(
                submission_id=submission_id,
                question_id=result.question_id,
                grade_result=result,
                reason="low_confidence",
            )
            self._items.append(item)
            return item
        if "needs_review" in result.flags:
            item = ReviewItem(
                submission_id=submission_id,
                question_id=result.question_id,
                grade_result=result,
                reason="flagged",
            )
            self._items.append(item)
            return item
        return None

    def pending(self) -> list[ReviewItem]:
        return [i for i in self._items if i.status == "pending"]
```

### Success Criteria
- [ ] Rubric parser loads YAML and returns typed GradingRubric
- [ ] OpenAI provider sends prompt and parses JSON response
- [ ] Grading engine grades a single question end-to-end
- [ ] Review queue flags items below confidence threshold
- [ ] Output parser handles malformed LLM responses gracefully
- [ ] All tests pass with mocked LLM responses

---

## Wave 3: Workflow Orchestrator

**Goal**: Full pipeline: fetch -> grade -> review -> export -> upload.
**Dependencies**: Wave 1 (Client) + Wave 2 (Grader) complete.
**Parallelizable**: Internal tasks are sequential (pipeline logic).

### Tasks

| ID | Task | File(s) | Commit | Category | Deps |
|----|------|---------|--------|----------|------|
| 3.1 | Pipeline orchestrator | `src/gradescope_autograde/workflow/pipeline.py` | `feat(workflow): add grading pipeline` | `business-logic` | 1.7, 2.11 |
| 3.2 | CSV exporter | `src/gradescope_autograde/workflow/export.py` | `feat(workflow): add CSV/Gradescope CSV export` | `quick` | 3.1 |
| 3.3 | Progress tracker | `src/gradescope_autograde/workflow/progress.py` | `feat(workflow): add progress tracking with resume` | `quick` | 3.1 |
| 3.4 | Dry-run mode | `src/gradescope_autograde/workflow/pipeline.py` | `feat(workflow): add dry-run mode` | `quick` | 3.1 |
| 3.5 | Workflow tests | `tests/unit/test_workflow.py` | `test(workflow): add pipeline and export tests` | `quick` | 3.4 |
| 3.6 | Integration test | `tests/integration/test_pipeline.py` | `test: add end-to-end pipeline integration test` | `deep` | 3.5 |

### Pipeline Design

```python
class GradingPipeline:
    def __init__(self, client: GSClient, engine: GradingEngine,
                 config: Config, dry_run: bool = False):
        self.client = client
        self.engine = engine
        self.config = config
        self.dry_run = dry_run
        self.progress = ProgressTracker()

    async def run(self, course_id: str, assignment_id: str) -> PipelineResult:
        # 1. Fetch submissions
        submissions = self.client.list_submissions(course_id, assignment_id)
        submissions = self.progress.filter_remaining(submissions)

        results = []
        for sub in submissions:
            # 2. Fetch content
            content = self.client.get_submission_content(course_id, assignment_id, sub.id)

            # 3. Grade with LLM
            grade_results = await self.engine.grade_submission(sub.id, content)

            # 4. Check review queue
            needs_review = self.engine.review_queue.check_all(sub.id, grade_results)

            # 5. Upload if confident and not dry-run
            if not needs_review and not self.dry_run:
                total_score = sum(r.score for r in grade_results)
                feedback = "\n\n".join(r.feedback for r in grade_results)
                self.client.upload_grade(course_id, assignment_id, sub.id, total_score, feedback)

            self.progress.mark_done(sub.id)
            results.append(PipelineResult(submission=sub, grades=grade_results, review=needs_review))

        return PipelineResultCollection(results)
```

### Export Formats

```python
def export_gradescope_csv(results: list[PipelineResult], path: Path) -> None:
    """Export in Gradescope bulk-upload CSV format:
    First Name,Last Name,SID,Email,Question 1 Score,Question 1 Feedback,...
    """

def export_csv(results: list[PipelineResult], path: Path) -> None:
    """Standard CSV export for analysis."""

def export_json(results: list[PipelineResult], path: Path) -> None:
    """Full JSON export with all grading details."""
```

### Progress Tracking (Resume)

```python
class ProgressTracker:
    def __init__(self, state_file: Path | None = None):
        self.state_file = state_file
        self._completed: set[str] = set()
        self._load()

    def mark_done(self, submission_id: str) -> None:
        self._completed.add(submission_id)
        self._save()

    def filter_remaining(self, submissions: list[Submission]) -> list[Submission]:
        return [s for s in submissions if s.id not in self._completed]
```

### Success Criteria
- [ ] Pipeline fetches, grades, and exports in correct order
- [ ] Dry-run mode skips upload step
- [ ] Progress tracker saves/resumes state across runs
- [ ] Gradescope CSV format matches expected upload format
- [ ] Integration test runs full pipeline with mocked services

---

## Wave 4: CLI

**Goal**: Click-based CLI with all user-facing commands.
**Dependencies**: Wave 3 complete.

### Tasks

| ID | Task | File(s) | Commit | Category | Deps |
|----|------|---------|--------|----------|------|
| 4.1 | CLI entrypoint + config | `src/gradescope_autograde/cli/main.py` | `feat(cli): add Click entrypoint with config` | `quick` | 3.5 |
| 4.2 | login command | `src/gradescope_autograde/cli/commands/login.py` | `feat(cli): add login command` | `quick` | 4.1 |
| 4.3 | list command | `src/gradescope_autograde/cli/commands/list.py` | `feat(cli): add list courses/assignments/submissions` | `quick` | 4.1 |
| 4.4 | grade command | `src/gradescope_autograde/cli/commands/grade.py` | `feat(cli): add grade command with pipeline` | `business-logic` | 4.1 |
| 4.5 | upload command | `src/gradescope_autograde/cli/commands/upload.py` | `feat(cli): add upload command` | `quick` | 4.1 |
| 4.6 | review command | `src/gradescope_autograde/cli/commands/review.py` | `feat(cli): add interactive review command` | `business-logic` | 4.1 |
| 4.7 | Rich output formatting | `src/gradescope_autograde/cli/output.py` | `feat(cli): add Rich tables and progress bars` | `visual-engineering` | 4.1 |
| 4.8 | CLI tests | `tests/unit/test_cli.py` | `test(cli): add CLI command tests` | `quick` | 4.6 |

### CLI Commands

```
gs-autograde login                          # Interactive auth (email/password or cookie)
gs-autograde list courses                   # List all courses
gs-autograde list assignments COURSE_ID     # List assignments for a course
gs-autograde list submissions COURSE_ID ASSIGNMENT_ID  # List submissions
gs-autograde grade COURSE_ID ASSIGNMENT_ID  # Full grading pipeline
  --dry-run                                 # Preview without uploading
  --batch-size N                            # Limit submissions per run
  --resume                                  # Resume from last checkpoint
  --rubric PATH                             # Custom rubric file
gs-autograde upload COURSE_ID ASSIGNMENT_ID # Upload grades from CSV
  --file PATH                               # CSV file to upload
gs-autograde review                         # Interactive review of flagged items
  --file PATH                               # Review queue file
gs-autograde export COURSE_ID ASSIGNMENT_ID # Export grades
  --format csv|json|gradescope_csv          # Output format
  --output PATH                             # Output file path
```

### Success Criteria
- [ ] All commands parse arguments correctly
- [ ] `login` saves cookies for subsequent commands
- [ ] `list` displays Rich tables
- [ ] `grade` runs full pipeline with progress bar
- [ ] `review` shows flagged items with accept/reject options
- [ ] CLI tests use Click's CliRunner

---

## Wave 5: Browser Automation Fallback

**Goal**: Playwright-based fallback for operations HTTP client can't handle.
**Dependencies**: Wave 1 complete (to identify gaps).
**Parallelizable**: YES — can run in parallel with Wave 2-4.

### Tasks

| ID | Task | File(s) | Commit | Category | Deps |
|----|------|---------|--------|----------|------|
| 5.1 | Playwright client base | `src/gradescope_autograde/client/browser_client.py` | `feat(client): add Playwright browser fallback` | `business-logic` | 1.7 |
| 5.2 | Cookie extraction | `src/gradescope_autograde/client/browser_client.py` | `feat(client): add browser cookie extraction` | `quick` | 5.1 |
| 5.3 | Browser client tests | `tests/unit/test_browser_client.py` | `test(client): add browser client tests` | `quick` | 5.2 |

### Browser Client Design

```python
class BrowserClient:
    """Playwright-based fallback for operations the HTTP client can't handle."""

    async def extract_cookies(self, browser: str = "chrome") -> str:
        """Extract Gradescope cookies from browser profile."""

    async def login_and_extract_cookies(self, email: str, password: str) -> str:
        """Full browser login flow, returns cookie string."""

    async def download_submission(self, course_id: str, assignment_id: str,
                                  submission_id: str) -> Path:
        """Download submission PDF via browser automation."""
```

### Success Criteria
- [ ] Can extract cookies from Chrome/Firefox profiles
- [ ] Login flow works with MFA (manual intervention)
- [ ] Cookie string is compatible with GSSession.login_with_cookie()

---

## Wave 6: Integration & Polish

**Goal**: End-to-end validation, error handling, documentation.
**Dependencies**: All previous waves complete.

### Tasks

| ID | Task | File(s) | Commit | Category | Deps |
|----|------|---------|--------|----------|------|
| 6.1 | Error handling hardening | All modules | `fix: add comprehensive error handling` | `deep` | 5.3 |
| 6.2 | Logging setup | `src/gradescope_autograde/logging.py` | `feat: add structured logging` | `quick` | — |
| 6.3 | End-to-end smoke test | `tests/e2e/test_smoke.py` | `test: add e2e smoke test with recorded session` | `deep` | 6.1 |
| 6.4 | Type checking pass | All modules | `fix: resolve mypy strict errors` | `quick` | 6.1 |
| 6.5 | Ruff formatting pass | All modules | `style: ruff format and lint fixes` | `quick` | 6.4 |

### Success Criteria
- [ ] `ruff check .` passes with zero errors
- [ ] `mypy --strict src/` passes with zero errors
- [ ] All unit tests pass
- [ ] Integration test passes with mocked services
- [ ] E2E test passes with recorded HTTP cassettes

---

## Dependency Graph

```
Wave 0: [0.1 Models] -> [0.2 Grading Models] -> [0.3 Config]
         [0.4 Test Infra] -> [0.5 Fix Auth] -> [0.6 Auth Tests]

Wave 1 (Client):  [1.1 Base] -> [1.3 Assignments] -> [1.4 Submissions] -> [1.5 Content] -> [1.6 Upload]
                   +-> [1.2 Tests]  +-> [1.8 Rate Limiter]  +-> [1.7 Full Tests]

Wave 2 (Grader):  [2.1 Rubric] -> [2.7 Prompt] -> [2.8 Parser] -> [2.9 Engine] -> [2.10 Review]
                   +-> [2.3 LLM Abs] -> [2.4 OpenAI] -> [2.5 Anthropic] -> [2.6 Ollama]
                   +-> [2.2 Tests]  +-> [2.12 Provider Tests]  +-> [2.11 Grader Tests]

Wave 3 (Workflow): [3.1 Pipeline] -> [3.2 Export] -> [3.3 Progress] -> [3.4 Dry-run] -> [3.5 Tests] -> [3.6 Integration]

Wave 4 (CLI):     [4.1 Entrypoint] -> [4.2 login, 4.3 list, 4.4 grade, 4.5 upload, 4.6 review] -> [4.7 Rich] -> [4.8 Tests]

Wave 5 (Browser): [5.1 Base] -> [5.2 Cookies] -> [5.3 Tests]

Wave 6 (Polish):  [6.1 Errors] -> [6.2 Logging] -> [6.3 E2E] -> [6.4 Mypy] -> [6.5 Ruff]
```

---

## Parallelization Map

```
Week 1:  Wave 0 (all tasks) — foundation
Week 2:  Wave 1 (Client) || Wave 2 (Grader) — parallel tracks
Week 3:  Wave 3 (Workflow) — merge point
Week 4:  Wave 4 (CLI) || Wave 5 (Browser) — parallel tracks
Week 5:  Wave 6 (Polish) — finalization
```

---

## Testing Strategy

### Unit Tests (per module)
- **Models**: Validation, serialization, edge cases (None fields, empty lists)
- **Client**: Mock HTTP responses with `responses` or `pytest-httpx`
- **Grader**: Mock LLM responses, test prompt generation, test output parsing
- **Workflow**: Mock client + grader, test pipeline logic
- **CLI**: Click's `CliRunner` with mocked dependencies

### Integration Tests
- **Pipeline**: Mock GSClient + real GradingEngine with mock LLM
- **Export**: Real data -> verify CSV/JSON output format
- **Config**: Real YAML files -> verify loading

### E2E Tests
- **Recorded sessions**: Use `vcrpy` or manual JSON cassettes for HTTP replay
- **Smoke test**: Login -> list courses -> list assignments -> grade 1 submission -> export

### Test File Structure
```
tests/
├── conftest.py              # Shared fixtures, mock factories
├── fixtures/
│   ├── courses.html         # Sample Gradescope HTML
│   ├── assignments.html
│   ├── submissions.html
│   ├── rubric.yaml          # Sample rubric
│   └── llm_response.json    # Sample LLM output
├── unit/
│   ├── test_models.py
│   ├── test_session.py
│   ├── test_client.py
│   ├── test_rubric_parser.py
│   ├── test_grader.py
│   ├── test_providers.py
│   ├── test_workflow.py
│   └── test_cli.py
├── integration/
│   └── test_pipeline.py
└── e2e/
    └── test_smoke.py
```

---

## Atomic Commit Strategy

Each commit is:
1. **Self-contained**: Compiles, passes lint, passes its own tests
2. **Single-purpose**: One logical change per commit
3. **Reversible**: Can be reverted without breaking other commits

### Commit Message Convention
```
<type>(<scope>): <description>

Types: feat, fix, test, refactor, style, docs
Scopes: models, transport, client, grader, workflow, cli
```

### Commit Sequence (38 commits)
```
Wave 0 (6 commits):
  feat(models): add core domain models
  feat(models): add grading domain models
  feat(config): add YAML config loader
  test: add test infrastructure and fixtures
  fix(transport): add CSRF token scraping to login
  test(transport): add session auth tests

Wave 1 (8 commits):
  feat(client): add GSClient with list_courses
  test(client): add client course listing tests
  feat(client): add list_assignments
  feat(client): add list_submissions
  feat(client): add submission content fetcher
  feat(client): add grade upload
  test(client): add full client CRUD tests
  feat(client): add rate limiter with backoff

Wave 2 (12 commits):
  feat(grader): add YAML rubric parser
  test(grader): add rubric parser tests
  feat(grader): add LLM provider abstraction
  feat(grader): add OpenAI provider
  feat(grader): add Anthropic provider
  feat(grader): add Ollama provider
  feat(grader): add structured prompt builder
  feat(grader): add structured JSON output parser
  feat(grader): add grading engine orchestrator
  feat(grader): add review queue for low-confidence
  test(grader): add grading engine tests
  test(grader): add LLM provider tests

Wave 3 (6 commits):
  feat(workflow): add grading pipeline
  feat(workflow): add CSV/Gradescope CSV export
  feat(workflow): add progress tracking with resume
  feat(workflow): add dry-run mode
  test(workflow): add pipeline and export tests
  test: add end-to-end pipeline integration test

Wave 4 (8 commits):
  feat(cli): add Click entrypoint with config
  feat(cli): add login command
  feat(cli): add list courses/assignments/submissions
  feat(cli): add grade command with pipeline
  feat(cli): add upload command
  feat(cli): add interactive review command
  feat(cli): add Rich tables and progress bars
  test(cli): add CLI command tests

Wave 5 (3 commits):
  feat(client): add Playwright browser fallback
  feat(client): add browser cookie extraction
  test(client): add browser client tests

Wave 6 (5 commits):
  fix: add comprehensive error handling
  feat: add structured logging
  test: add e2e smoke test with recorded session
  fix: resolve mypy strict errors
  style: ruff format and lint fixes
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Gradescope HTML structure changes | Abstract HTML parsing into separate parser module; easy to update |
| LLM outputs malformed JSON | Robust output parser with retry + fallback to raw text |
| Rate limiting / IP block | Configurable delay, exponential backoff, cookie rotation |
| CSRF token format changes | Fallback to browser cookie extraction (Wave 5) |
| Ollama local model quality | Confidence threshold + review queue catches bad grades |

---

## Estimated Effort

| Wave | Tasks | Est. Time | Parallel? |
|------|-------|-----------|-----------|
| 0: Foundation | 6 | 2-3 hours | Sequential (internal) |
| 1: Client | 8 | 3-4 hours | Parallel with Wave 2 |
| 2: Grader | 12 | 4-5 hours | Parallel with Wave 1 |
| 3: Workflow | 6 | 2-3 hours | Sequential |
| 4: CLI | 8 | 2-3 hours | Parallel with Wave 5 |
| 5: Browser | 3 | 1-2 hours | Parallel with Wave 4 |
| 6: Polish | 5 | 1-2 hours | Sequential |
| **Total** | **48** | **15-22 hours** | **~12-16 hours with parallelization** |
