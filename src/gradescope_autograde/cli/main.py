from __future__ import annotations

import json
import sys
from pathlib import Path

import click
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from gradescope_autograde.config import load_config

console = Console()
error_console = Console(stderr=True)


def _error(message: str) -> None:
    error_console.print(f"[bold red]Error:[/bold red] {message}")
    sys.exit(1)


def _success(message: str) -> None:
    console.print(f"[bold green]Success:[/bold green] {message}")


def _create_session(config_path: str):
    from gradescope_autograde.transport.session import GSSession

    cfg = load_config(config_path)
    session = GSSession(
        base_url=cfg.gradescope.base_url,
        request_delay=cfg.gradescope.request_delay,
        max_retries=cfg.gradescope.max_retries,
    )

    cookie_path = Path(".cookies/session.txt")
    if cookie_path.exists():
        session.load_cookies(cookie_path)
    elif cfg.auth.cookie:
        session.login_with_cookie(cfg.auth.cookie)
    elif cfg.auth.email and cfg.auth.password:
        if not session.login(cfg.auth.email, cfg.auth.password):
            _error("Login failed. Check credentials.")
    else:
        _error("No credentials found. Run `gs-autograde login` first.")

    return session, cfg


@click.group()
@click.option("--config", "-c", default="config/config.yaml", help="Path to config file")
@click.pass_context
def cli(ctx: click.Context, config: str) -> None:
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config


@cli.command()
@click.option("--email", "-e", default=None, help="Gradescope email")
@click.option("--password", "-p", default=None, help="Gradescope password")
@click.option("--cookie", "-C", default=None, help="Session cookie string")
@click.option("--browser", "-b", is_flag=True, help="Open browser for manual login (OAuth-like)")
@click.option("--timeout", type=int, default=120, help="Browser login timeout in seconds")
@click.pass_context
def login(
    ctx: click.Context,
    email: str | None,
    password: str | None,
    cookie: str | None,
    browser: bool,
    timeout: int,
) -> None:
    """Authenticate with Gradescope.

    Supports three login methods:
    1. Email + password (auto-fills login form)
    2. Cookie string (from browser DevTools)
    3. Browser login (opens browser, you log in manually, cookies auto-captured)
    """
    from gradescope_autograde.transport.session import GSSession

    if browser:
        from gradescope_autograde.client.browser import BrowserCookieExtractor

        cookie = BrowserCookieExtractor.from_interactive_browser(timeout=timeout)
        if not cookie:
            console.print("[red]Browser login failed or timed out.[/red]")
            return

    if cookie:
        session = GSSession()
        session.login_with_cookie(cookie)
        session.save_cookies(Path(".cookies/session.txt"))
        console.print("[green]✅ Logged in with cookie![/green]")
        return

    if not email:
        email = click.prompt("Email")
    if not password:
        password = click.prompt("Password", hide_input=True)

    session = GSSession()
    try:
        if session.login(email, password):
            session.save_cookies(Path(".cookies/session.txt"))
            console.print("[green]✅ Login successful![/green]")
        else:
            console.print("[red]❌ Login failed. Check your credentials.[/red]")
            console.print("[yellow]💡 Try: gs-autograde login --browser[/yellow]")
    except Exception as exc:
        console.print(f"[red]❌ Login error: {exc}[/red]")
        console.print("[yellow]💡 Try: gs-autograde login --browser[/yellow]")


@cli.command()
@click.pass_context
def models(ctx: click.Context) -> None:
    from gradescope_autograde.grader.providers import (
        LMStudioProvider,
        ModelRegistry,
        OpenCodeGoProvider,
    )

    registry = ModelRegistry()
    registry.register("opencode-go", OpenCodeGoProvider())
    registry.register("lmstudio", LMStudioProvider())

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("Discovering models...", total=None)
        all_models = registry.discover_all()

    table = Table(title="Available AI Models", show_lines=True)
    table.add_column("Provider", style="cyan")
    table.add_column("Model", style="green")
    table.add_column("Context", justify="right")
    table.add_column("Multimodal", justify="center")
    table.add_column("Loaded", justify="center")

    for m in all_models:
        ctx_len = m.get("context_length", 0)
        ctx_str = f"{ctx_len:,}" if ctx_len else "—"
        multi = "Yes" if m.get("multimodal") else "No"
        loaded_val = m.get("loaded")
        if loaded_val is None:
            loaded_str = "—"
        else:
            loaded_str = "[green]Yes[/green]" if loaded_val else "[dim]No[/dim]"

        name = m.get("name") or m.get("display_name") or m.get("id", "—")
        if m.get("id") == "__error__":
            name = f"[red]{name}[/red]"

        table.add_row(m.get("provider", "?"), name, ctx_str, multi, loaded_str)

    console.print(table)


@cli.command("list")
@click.argument("resource", type=click.Choice(["courses", "assignments", "submissions"]))
@click.argument("ids", nargs=-1)
@click.pass_context
def list_resources(ctx: click.Context, resource: str, ids: tuple[str, ...]) -> None:
    from gradescope_autograde.client.client import GSClient

    config_path: str = ctx.obj["config_path"]
    session, cfg = _create_session(config_path)
    client = GSClient(session)

    try:
        if resource == "courses":
            items = client.list_courses()
            table = Table(title="Courses", show_lines=True)
            table.add_column("ID", style="cyan")
            table.add_column("Name", style="green")
            for item in items:
                table.add_row(str(item.get("id", "")), item.get("name", ""))
            console.print(table)

        elif resource == "assignments":
            if len(ids) < 1:
                _error("Usage: gs-autograde list assignments COURSE_ID")
            course_id = ids[0]
            items = client.list_assignments(course_id)
            table = Table(title=f"Assignments — Course {course_id}", show_lines=True)
            table.add_column("ID", style="cyan")
            table.add_column("Name", style="green")
            for item in items:
                table.add_row(str(item.get("id", "")), item.get("name", ""))
            console.print(table)

        elif resource == "submissions":
            if len(ids) < 2:
                _error("Usage: gs-autograde list submissions COURSE_ID ASSIGNMENT_ID")
            course_id, assignment_id = ids[0], ids[1]
            items = client.list_submissions(course_id, assignment_id)
            table = Table(title=f"Submissions — Assignment {assignment_id}", show_lines=True)
            table.add_column("ID", style="cyan")
            table.add_column("Student", style="green")
            table.add_column("Email")
            table.add_column("Score")
            for item in items:
                table.add_row(
                    str(item.get("id", "")),
                    item.get("student_name", ""),
                    item.get("student_email", ""),
                    item.get("score", ""),
                )
            console.print(table)

    except Exception as exc:
        _error(f"Failed to list {resource}: {exc}")


@cli.command("parse-pdf")
@click.argument("pdf_path", type=click.Path(exists=True))
@click.option("--separator", default="## Question", help="Question separator string")
@click.option("--output", "-o", default=None, help="Save rubric YAML template to this path")
@click.pass_context
def parse_pdf(ctx: click.Context, pdf_path: str, separator: str, output: str | None) -> None:
    from gradescope_autograde.grader.pdf_parser import parse_reference_pdf, split_into_questions, extract_text_from_pdf

    try:
        pages = extract_text_from_pdf(pdf_path)
        raw_questions = split_into_questions(pages, separator=separator)
        parsed = parse_reference_pdf(pdf_path)
    except Exception as exc:
        _error(f"Failed to parse PDF: {exc}")

    for q in parsed:
        num = q["question_number"]
        text = q["text"]
        ref = q.get("reference_answer", "")
        pts = q.get("max_points", 10.0)

        content_parts = [f"[bold]Question {num}[/bold] ({pts} pts)\n{text}"]
        if ref:
            content_parts.append(f"\n[dim]Reference Answer:[/dim]\n{ref}")
        panel = Panel("\n".join(content_parts), title=f"Q{num}", border_style="blue")
        console.print(panel)

    _success(f"Extracted {len(parsed)} questions from {pdf_path}")

    if output:
        rubric: dict = {
            "questions": [
                {
                    "id": f"q{q['question_number']}",
                    "title": f"Question {q['question_number']}",
                    "max_points": q.get("max_points", 10.0),
                    "type": "short_answer",
                    "text": q["text"],
                    "reference_answer": q.get("reference_answer", ""),
                    "extra_instructions": q.get("extra_instructions", ""),
                    "rubric": [
                        {
                            "name": "correctness",
                            "points": q.get("max_points", 10.0),
                            "description": "Answer is correct and complete",
                        }
                    ],
                }
                for q in parsed
            ]
        }
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(yaml.dump(rubric, default_flow_style=False, allow_unicode=True))
        _success(f"Rubric template saved to {output}")


@cli.command()
@click.argument("course_id")
@click.argument("assignment_id")
@click.option("--rubric", "-r", required=True, type=click.Path(exists=True), help="Path to rubric file (.yaml/.yml/.pdf/.tex)")
@click.option("--dry-run", is_flag=True, help="Grade locally without uploading")
@click.option("--upload", is_flag=True, help="Upload grades to Gradescope after grading (overrides --dry-run)")
@click.option("--with-pages", is_flag=True, help="Include [Page N of M] markers for unmapped PDF submissions")
@click.option("--extraction", type=click.Choice(["auto", "text", "ocr", "multimodal"]), default="auto", help="PDF text extraction: auto (default), text (LaTeX PDFs), ocr (handwriting), or multimodal (images for mimo-v2.5)")
@click.option("--provider", default="opencode-go", help="LLM provider name")
@click.option("--model", default=None, help="Model ID to use")
@click.option("--questions", "-q", default=None, help="Comma-separated question IDs to grade (e.g. 'q1,q3'). Default: all. Use 'rubric list-questions <file>' to see IDs.")
@click.option("--gen-rubric", is_flag=True, help="Generate rubric from question/answer PDFs instead of loading one")
@click.option("--rubric-gen-model", default="deepseek-v4-pro", help="Model for rubric generation (default: deepseek-v4-pro)")
@click.option("--rubric-gen-provider", default="opencode-go", help="Provider for rubric generation (opencode-go or lmstudio)")
@click.option("--gs-question-id", default=None, help="Numeric Gradescope question ID for upload (e.g. 71029768)")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed error messages")
@click.pass_context
def grade(
    ctx: click.Context,
    course_id: str,
    assignment_id: str,
    rubric: str,
    dry_run: bool,
    upload: bool,
    with_pages: bool,
    extraction: str,
    provider: str,
    model: str | None,
    questions: str | None,
    gen_rubric: bool,
    rubric_gen_model: str,
    rubric_gen_provider: str,
    gs_question_id: str | None,
    verbose: bool,
) -> None:
    from gradescope_autograde.client.client import GSClient
    from gradescope_autograde.grader.engine import GradingEngine
    from gradescope_autograde.grader.providers import (
        LMStudioProvider,
        ModelRegistry,
        OpenCodeGoProvider,
    )
    from gradescope_autograde.grader.review import ReviewQueue
    from gradescope_autograde.workflow.export import export_grades_csv
    from gradescope_autograde.workflow.pipeline import Pipeline

    config_path: str = ctx.obj["config_path"]

    # Generate rubric from reference PDFs if --gen-rubric is set
    if gen_rubric:
        if verbose:
            error_console.print(f"[dim]Generating rubric using {rubric_gen_provider}/{rubric_gen_model}...[/dim]")
        from gradescope_autograde.grader.rubric_generator import generate_rubric as _gen_rubric

        session, cfg = _create_session(config_path)
        answer_pdf = rubric
        question_pdf = rubric.replace("ans", "")
        if not Path(question_pdf).exists():
            question_pdf = rubric  # fallback: use rubric path as question PDF
            answer_pdf = None
        rubric_data = _gen_rubric(
            question_pdf=question_pdf,
            answer_pdf=answer_pdf,
            extra_instructions="",
            model=rubric_gen_model,
            api_key=cfg.llm.api_key or None,
            provider_type=rubric_gen_provider if rubric_gen_provider != "opencode-go" else "opencode-go",
        )
        if verbose:
            error_console.print(f"[dim]Generated rubric with {len(rubric_data.get('questions',[]))} question(s)[/dim]")
    else:
        from gradescope_autograde.grader.rubric_parser import load_rubric as _load_rubric
        rubric_data = _load_rubric(rubric)

    session, cfg = _create_session(config_path)
    client = GSClient(session)

    registry = ModelRegistry()
    raw_key = cfg.llm.api_key
    if raw_key and not raw_key.startswith("${"):
        console.print("[dim]OpenCode Go API key: loaded from config/env[/dim]")
    elif verbose:
        error_console.print("[yellow]OpenCode Go API key: NOT SET — set OPENCODE_GO_API_KEY or use .env[/yellow]")
    registry.register("opencode-go", OpenCodeGoProvider(
        model=model or cfg.llm.model,
        api_key=raw_key or None,
    ))
    registry.register("lmstudio", LMStudioProvider(model=model))

    try:
        llm_provider = registry.get_provider(provider)
    except KeyError as exc:
        _error(str(exc))

    engine = GradingEngine(provider=llm_provider, temperature=cfg.llm.temperature)
    review_queue = ReviewQueue(threshold=cfg.workflow.review_threshold)
    pipeline = Pipeline(client=client, engine=engine, review_queue=review_queue)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task("Grading submissions...", total=None)
        q_ids = questions.split(",") if questions else None
        # --upload overrides --dry-run
        effective_upload = None
        if upload:
            effective_upload = True
        elif dry_run:
            effective_upload = False
        result = pipeline.run(
            course_id=course_id,
            assignment_id=assignment_id,
            rubric=rubric_data,
            dry_run=dry_run,
            question_ids=q_ids,
            verbose=verbose,
            upload=effective_upload,
            with_pages=with_pages,
            extraction=extraction,
            gs_question_id=gs_question_id,
            log_func=lambda msg, v: error_console.print(f"[dim]{msg}[/dim]") if v else None,
        )
        progress.update(task, description="Grading complete!", completed=100)

    summary = result["summary"]
    table = Table(title="Grading Summary", show_lines=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="green")
    table.add_row("Total", str(summary.get("total", 0)))
    table.add_row("Completed", str(summary.get("completed", 0)))
    table.add_row("Failed", str(summary.get("failed", 0)))
    table.add_row("Needs Review", str(result.get("review_count", 0)))
    console.print(table)

    output_dir = Path(cfg.output.grades_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results_path = output_dir / f"{course_id}_{assignment_id}_results.json"
    results_path.write_text(json.dumps(result["results"], indent=2, ensure_ascii=False))
    _success(f"Results saved to {results_path}")

    if dry_run:
        console.print("[yellow]Dry run — no grades were uploaded.[/yellow]")


@cli.command()
@click.argument("course_id")
@click.argument("assignment_id")
@click.option("--results", "-r", required=True, type=click.Path(exists=True), help="Path to results JSON or CSV")
@click.option("--gs-question-id", default=None, help="Numeric Gradescope question ID (e.g. 71029768 for Q4)")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed upload progress")
@click.pass_context
def upload(ctx: click.Context, course_id: str, assignment_id: str, results: str, gs_question_id: str | None, verbose: bool) -> None:
    from gradescope_autograde.client.client import GSClient

    config_path: str = ctx.obj["config_path"]
    session, _cfg = _create_session(config_path)
    client = GSClient(session)

    # Load results - support JSON and CSV
    rpath = Path(results)
    if rpath.suffix.lower() == ".csv":
        import csv
        with rpath.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            data = [row for row in reader]
        if verbose:
            error_console.print(f"[dim]Loaded {len(data)} rows from CSV[/dim]")
    else:
        with rpath.open(encoding="utf-8") as fh:
            data = json.load(fh)
        if verbose:
            error_console.print(f"[dim]Loaded {len(data)} entries from JSON[/dim]")

    # Get question submission mapping if gs_question_id is provided
    qs_map: dict[str, str] = {}
    if gs_question_id:
        if verbose:
            error_console.print(f"[dim]Fetching submission mapping for question {gs_question_id}...[/dim]")
        qs_map = client.get_question_submissions_map(course_id, gs_question_id)
        if verbose:
            error_console.print(f"[dim]Found {len(qs_map)} students in question submission list[/dim]")

    success_count = 0
    fail_count = 0
    skipped = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task(f"Uploading {len(data)} grades...", total=len(data))
        for entry in data:
            student_name = entry.get("student_name") or entry.get("Student Name") or entry.get("name", "")
            score = float(entry.get("score") or entry.get("Score") or 0)
            feedback = entry.get("feedback") or entry.get("Feedback", "")

            # Determine question submission ID
            qs_id = ""
            if gs_question_id and student_name in qs_map:
                qs_id = qs_map[student_name]
            else:
                qs_id = str(entry.get("submission_id") or entry.get("Submission ID", ""))

            if not qs_id:
                if verbose:
                    error_console.print(f"  [yellow]No submission ID for {student_name}, skipping[/yellow]")
                skipped += 1
                progress.advance(task)
                continue

            try:
                ok = client.submit_grade(
                    course_id, assignment_id, qs_id,
                    gs_question_id or str(entry.get("question_id", "")),
                    score, feedback,
                )
                if ok:
                    success_count += 1
                    if verbose:
                        error_console.print(f"  [green]✓ {student_name}: {score} pts[/green]")
                else:
                    fail_count += 1
                    if verbose:
                        error_console.print(f"  [red]✗ {student_name}: upload failed[/red]")
            except Exception:
                fail_count += 1
                if verbose:
                    import traceback
                    error_console.print(f"  [red]✗ {student_name}: {traceback.format_exc()}[/red]")

            progress.advance(task)

    table = Table(title="Upload Summary", show_lines=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="green")
    table.add_row("Uploaded", str(success_count))
    table.add_row("Failed", str(fail_count))
    console.print(table)

    if fail_count:
        _error(f"{fail_count} grades failed to upload.")
    else:
        _success(f"All {success_count} grades uploaded.")


@cli.command()
@click.option("--state-file", default=".state/review_queue.json", help="Path to review queue state file")
@click.pass_context
def review(ctx: click.Context, state_file: str) -> None:
    from gradescope_autograde.grader.review import ReviewQueue

    state_path = Path(state_file)
    if not state_path.exists():
        _error(f"Review queue not found at {state_file}. Run `grade` first.")

    with open(state_path, encoding="utf-8") as fh:
        items = json.load(fh)

    if not items:
        _success("No items in review queue.")
        return

    queue = ReviewQueue()
    queue._items = items

    console.print(f"[bold]Review Queue[/bold] — {len(items)} items\n")

    for idx, item in enumerate(items):
        status = item.get("status", "pending")
        if status != "pending":
            continue

        panel_content = (
            f"[bold]Submission:[/bold] {item.get('submission_id', '?')}\n"
            f"[bold]Question:[/bold] {item.get('question_id', '?')}\n"
            f"[bold]Score:[/bold] {item.get('score', '?')}\n"
            f"[bold]Confidence:[/bold] {item.get('confidence', '?')}\n"
            f"[bold]Reason:[/bold] {item.get('reason', '?')}\n"
            f"[bold]Feedback:[/bold]\n{item.get('feedback', '')}"
        )
        console.print(Panel(panel_content, title=f"Item {idx + 1}/{len(items)}", border_style="yellow"))

        action = console.input("[bold cyan]Approve (a) / Reject (r) / Skip (s)? [/bold cyan]").strip().lower()
        if action == "a":
            queue.approve(idx)
            _success("Approved.")
        elif action == "r":
            notes = console.input("[dim]Rejection notes (optional): [/dim]").strip()
            queue.reject(idx, notes)
            console.print("[bold red]Rejected.[/bold red]")
        else:
            console.print("[dim]Skipped.[/dim]")

    state_path.write_text(json.dumps(queue._items, indent=2, ensure_ascii=False))
    _success(f"Review state saved to {state_file}")


@cli.command()
@click.option("--results", "-r", required=True, type=click.Path(exists=True), help="Path to results JSON")
@click.option("--format", "fmt", type=click.Choice(["gradescope", "detailed", "json"]), default="gradescope", help="Export format")
@click.option("--output", "-o", default=None, help="Output file path (default: auto)")
@click.pass_context
def export(ctx: click.Context, results: str, fmt: str, output: str | None) -> None:
    from gradescope_autograde.workflow.export import export_grades_csv

    results_path = Path(results)
    with open(results_path, encoding="utf-8") as fh:
        data = json.load(fh)

    if output:
        out_path = output
    else:
        ext = "json" if fmt == "json" else "csv"
        out_path = str(results_path.with_suffix(f".{fmt}.{ext}"))

    try:
        written = export_grades_csv(data, out_path, format_type=fmt)
        _success(f"Exported {len(data)} results to {written}")
    except Exception as exc:
        _error(f"Export failed: {exc}")


@cli.command()
@click.option("--host", default="127.0.0.1", help="Host to bind to")
@click.option("--port", default=8080, help="Port to listen on")
@click.pass_context
def gui(ctx: click.Context, host: str, port: int) -> None:
    """Launch web GUI in browser."""
    from gradescope_autograde.gui import run_gui

    config_path: str = ctx.obj["config_path"]
    run_gui(host=host, port=port, config_path=config_path)


@cli.command("list-questions")
@click.argument("source", required=False, default=None)
@click.option("--course", "-c", default=None, help="Course ID (for fetching from Gradescope)")
@click.option("--assignment", "-a", default=None, help="Assignment ID (for fetching from Gradescope)")
@click.pass_context
def list_questions_cli(ctx: click.Context, source: str | None, course: str | None, assignment: str | None) -> None:
    """List questions from a rubric file or a Gradescope assignment.

    \b
    Examples:
      # From a rubric YAML file:
      gs-autograde list-questions config/rubrics/default_rubric.yaml

      # From a Gradescope assignment (fetches review grades table):
      gs-autograde list-questions --course 1273022 --assignment 8113109
    """
    if source and Path(source).exists():
        from gradescope_autograde.grader.rubric_parser import list_rubric_questions as _lrq

        questions = _lrq(source)
        if not questions:
            _error("No questions found or unsupported format.")
        table = Table(title=f"Questions from rubric: {source}", show_lines=True)
        table.add_column("ID", style="cyan")
        table.add_column("Title", style="green")
        table.add_column("Max Points", justify="right")
        table.add_column("Type")
        for q in questions:
            table.add_row(
                q.get("id", "?"),
                q.get("title", "?")[:40],
                str(q.get("max_points", "?")),
                q.get("type", "?"),
            )
        console.print(table)
        return

    if course and assignment:
        config_path: str = ctx.obj["config_path"]
        session, _cfg = _create_session(config_path)
        from gradescope_autograde.client.client import GSClient
        client = GSClient(session)
        gs_questions = client.list_questions(course, assignment)
        if gs_questions:
            table = Table(title=f"Questions from Gradescope (course {course}, assignment {assignment})", show_lines=True)
            table.add_column("ID", style="cyan")
            table.add_column("Name", style="green")
            for q in gs_questions:
                table.add_row(q.get("id", "?"), q.get("name", "")[:60])
            console.print(table)
        else:
            console.print("[yellow]No per-question columns in Gradescope for this assignment.[/yellow]")
            console.print("[yellow]Use 'gs-autograde list-questions <rubric.yaml>' to see rubric questions.[/yellow]")
        return

    _error("Provide either a rubric file path, or --course and --assignment.")
    """List questions from a rubric file (YAML only)."""
    from gradescope_autograde.grader.rubric_parser import list_rubric_questions as _lrq

    questions = _lrq(rubric_path)
    if not questions:
        _error("No questions found or unsupported format (PDF/LaTeX rubrics not supported for listing).")
    table = Table(title=f"Questions from: {rubric_path}", show_lines=True)
    table.add_column("ID", style="cyan")
    table.add_column("Title", style="green")
    table.add_column("Max Points", justify="right")
    table.add_column("Type")
    for q in questions:
        table.add_row(
            q.get("id", "?"),
            q.get("title", "?")[:40],
            str(q.get("max_points", "?")),
            q.get("type", "?"),
        )
    console.print(table)


@cli.command()
@click.argument("message", required=False, default=None)
@click.option("--model", "-m", default="mimo-v2.5", help="Model to use (default: mimo-v2.5)")
@click.option("--provider", "-p", default="opencode-go", help="Provider: opencode-go or lmstudio")
def chat(message: str | None, model: str, provider: str) -> None:
    """Chat with OpenCode AI to operate the autograder via natural language.

    \b
    Examples:
      gs-autograde chat                              # interactive REPL
      gs-autograde chat "grade hw9 q4 for si120"     # single-shot
      gs-autograde chat -p lmstudio -m gemma4-12b    # use LM Studio
    """
    from gradescope_autograde.utils.opencode_utils import detect_opencode, get_install_instructions, generate_provider_config, generate_lmstudio_provider_config, merge_provider_to_config, run_chat

    detection = detect_opencode()
    if not detection["installed"]:
        console.print("[bold red]OpenCode CLI is not installed.[/bold red]")
        console.print(get_install_instructions())
        return

    console.print(f"[dim]OpenCode {detection.get('version', '?')} at {detection['path']}[/dim]")
    console.print(f"[dim]Provider: {provider}, Model: {model}[/dim]")

    # LM Studio: auto-start the server
    if provider == "lmstudio":
        try:
            from gradescope_autograde.lmstudio.manager import LmsManager
            from gradescope_autograde.lmstudio.manager import detect_lmstudio as _detect_lms
            lms_status = _detect_lms()
            if not lms_status.get("server_running"):
                console.print("[dim]LM Studio server not running. Starting...[/dim]")
                lm = LmsManager()
                if lm.ensure_running():
                    console.print("[green]LM Studio server started.[/green]")
                else:
                    console.print("[yellow]Could not start LM Studio server.[/yellow]")
            else:
                console.print("[dim]LM Studio server already running.[/dim]")
            if not detection.get("has_provider"):
                console.print("[yellow]LM Studio provider not in opencode config. Adding...[/yellow]")
                merge_provider_to_config(generate_lmstudio_provider_config(), "lmstudio")
        except Exception as e:
            console.print(f"[yellow]LM Studio setup warning: {e}[/yellow]")

    full_model = f"{provider}/{model}"

    # Single shot mode
    if message:
        console.print(f"[dim]Running: opencode run -m {full_model} {message}[/dim]")
        output = run_chat(message, model=full_model)
        console.print(output)
        return

    # Interactive REPL mode
    console.print("[bold]AI Chat Mode[/bold]")
    console.print("Type 'exit' or 'quit' to leave.\n")
    console.print(f"[dim]Model: {full_model}[/dim]\n")

    while True:
        try:
            msg = console.input("[bold cyan]You> [/bold cyan]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye![/dim]")
            break
        if not msg:
            continue
        if msg.lower() in ("exit", "quit", "q"):
            console.print("[dim]Goodbye![/dim]")
            break
        output = run_chat(msg, model=full_model)
        console.print(output)


@cli.command()
@click.pass_context
def tui(ctx: click.Context) -> None:
    from gradescope_autograde.tui import run_tui

    run_tui()
