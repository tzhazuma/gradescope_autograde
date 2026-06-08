# Gradescope Automation: Research Summary

## Key Finding: No Official Public API

Gradescope (acquired by Turnitin) provides **no public API** for external programmatic access.
All automation tools rely on one of three approaches:

| Approach | Reliability | Complexity | Cost |
|----------|------------|------------|------|
| 1. HTTP scraping (reverse-engineer internal endpoints) | High | Medium | Free |
| 2. Browser request interception (capture & replay) | Medium-High | Low-Medium | Free |
| 3. Computer-use / visual automation (AI + Playwright) | Medium | High | $$ per run |

**Recommended**: Layer 1 (HTTP scraping) as primary + Layer 3 (computer-use) as fallback for complex UI operations.

---

## Existing Tools & Libraries

### Python Libraries (HTTP scraping)

| Library | Stars | PyPI | Features |
|---------|-------|------|----------|
| [nyuoss/gradescope-api](https://github.com/nyuoss/gradescope-api) | 38 | `gradescopeapi` | Most complete: courses, assignments, extensions, uploads, FastAPI server option |
| [apozharski/gradescope-api](https://github.com/apozharski/gradescope-api) | 35 | N/A | Foundation for many other tools, AGPL licensed |
| [fullGSapi](https://pypi.org/project/fullGSapi/) | N/A | `fullGSapi` | Specifically for autograding exams, CLI included |

### Full Grading Pipelines

| Project | Approach | Status |
|---------|----------|--------|
| [LaTA](https://github.com/JesseRodriguez/LaTA) | Gradescope export → local Ollama LLM → LaTeX feedback PDFs | Production-tested (180 students, 8 assignments, Winter 2026) |
| [Auto-Gradescope](https://devpost.com/software/auto-gradescope) | GPT-4o + Selenium browser automation | Hackathon project (2025) |
| [Grade-Saver](https://github.com/Shrish-M/Grade-Saver) | Chrome extension for regrade requests | Catapult Hacks 2025 |

### Browser Extensions / Tools

| Tool | Use Case |
|------|----------|
| [Grade-Saver Chrome Extension](https://github.com/Shrish-M/Grade-Saver) | Auto-generates regrade requests using AI |
| [Proxyman](https://proxyman.io/) | macOS HTTPS proxy for intercepting API calls |
| [Charles Proxy](https://www.charlesproxy.com/) | Alternative HTTPS debugging proxy |

---

## Browser Request Interception Workflow

If building from scratch (or the reverse-engineered libraries break), here's the workflow:

1. **Login in browser** → Open Chrome DevTools → Network tab
2. **Filter by XHR/Fetch** → Identify API endpoints (e.g., `/api/v1/courses/{id}/assignments`)
3. **Copy as cURL** → Right-click request → Copy → Copy as cURL
4. **Extract auth** → Application tab → Cookies → `_gradescope_session`
5. **Replay in Python**:
   ```python
   session = requests.Session()
   session.cookies.set("_gradescope_session", "your-session-cookie")
   response = session.get("https://www.gradescope.com/api/v1/courses")
   ```

Key Gradescope internal endpoints (from reverse engineering):
- `GET /api/v1/courses` — list courses
- `GET /api/v1/courses/{id}/assignments` — list assignments
- `GET /api/v1/courses/{id}/assignments/{aid}/submissions` — list submissions
- `GET /api/v1/courses/{id}/assignments/{aid}/submissions/{sid}` — get submission PDF
- `POST /api/v1/courses/{id}/assignments/{aid}/submissions/{sid}/grade` — submit grade

**Note**: These endpoints are reverse-engineered and may change. Always have a fallback.

---

## Computer-Use / Visual Automation

### Tools Evaluated

| Tool | Approach | Cost | Viability |
|------|----------|------|-----------|
| [browser-use](https://github.com/browser-use/browser-use) (97K ⭐) | LLM agent + Playwright | LLM API costs per step | Good for complex multi-step flows |
| [Playwright](https://playwright.dev/) directly | Scripted browser automation | Free | Best for deterministic flows |
| [Stagehand](https://github.com/browserbase/stagehand) | AI + Playwright with self-healing | Free OSS + LLM costs | Good for locator robustness |
| Anthropic Computer Use | Claude controls desktop | Expensive per session | Overkill for repetitive grading |
| OpenAI Operator | GPT controls browser | Expensive, limited access | Too new, not reliable yet |

### Recommendation
For **repetitive** grading operations (same flow, 100+ students), **scripted Playwright** is best.
For **one-off** complex operations, **browser-use** with GPT-4o-mini is cost-effective.
**Computer Use is not recommended** for this use case — too expensive and unreliable for production grading.

---

## LLM Grading Best Practices

### Prompt Structure
```
You are grading [COURSE] - [ASSIGNMENT].

[QUESTION TEXT]

[RUBRIC - with explicit criteria and point values]

[STUDENT ANSWER]

Evaluate the student's answer against the rubric. Return structured JSON:
{
  "question_id": "q1",
  "score": <total_points>,
  "breakdown": [
    {"criterion": "...", "points_awarded": N, "max_points": M, "justification": "..."}
  ],
  "confidence": <0.0-1.0>,
  "feedback": "<constructive, specific feedback>",
  "flags": ["<any concerns: off_topic, incomplete, needs_review>"]
}
```

### Critical Parameters
- **temperature=0.1**: Low for grading consistency
- **Structured output / JSON mode**: Required for parsing
- **Confidence threshold**: < 0.7 → flag for human review
- **Rubric granularity**: Checklist-based rubrics outperform holistic rubrics

### Research Consensus
- LLMs match human accuracy on **structured tasks** with explicit rubrics
- Performance declines on **open-ended, creative, or subjective** assignments
- **Human-in-the-loop** reduces manual work by 40-90% while maintaining quality
- **Central tendency bias**: LLMs avoid extreme scores — calibrate with examples

---

## Architecture Decision

For this project, we use a **layered architecture**:

```
┌──────────────────────────────────────────┐
│         CLI / Workflow Orchestrator       │  ← User interface
├──────────────────────────────────────────┤
│            Grading Engine (LLM)           │  ← AI evaluation
├──────────────────────────────────────────┤
│         Gradescope Client (API)           │  ← Data operations
├──────────────────────────────────────────┤
│     Transport (HTTP Session / Auth)       │  ← Network layer
└──────────────────────────────────────────┘
```

- **Primary path**: HTTP scraping via `gradescopeapi`-inspired client
- **Fallback path**: Browser request interception (manual cookie extraction)
- **Last resort**: Playwright/browser-use visual automation
- **Grading intelligence**: OpenAI GPT-4o with structured JSON output
- **Local alternative**: Ollama with llama3.1 or similar for privacy
