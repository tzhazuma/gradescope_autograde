from __future__ import annotations

from nicegui import ui


def run_gui(host: str = "127.0.0.1", port: int = 8080, config_path: str = "config/config.yaml") -> None:
    """Launch the NiceGUI web interface for Gradescope AutoGrade.

    Args:
        host: Host to bind the web server to.
        port: Port to listen on.
        config_path: Path to the configuration YAML file.
    """

    @ui.page("/")
    def main_page() -> None:
        with ui.column().classes("w-full max-w-3xl mx-auto p-4"):
            ui.label("Gradescope AutoGrade").classes("text-3xl font-bold mb-4")
            ui.label("AI-Powered Automated Grading Assistant").classes(
                "text-lg text-gray-500 mb-8"
            )

            state: dict = {
                "course_id": None,
                "assignment_id": None,
                "question_pdf": None,
                "rubric_yaml": None,
                "rubric_data": None,
                "extra_instructions": "",
                "selected_model": "deepseek-v4-flash",
                "selected_provider": "opencode-go",
                "email": "",
                "password": "",
                "logged_in": False,
                "session": None,
                "verbose": False,
                "upload": False,
                "with_pages": False,
                "extraction": "auto",
                "courses": [],
                "assignments": [],
                "results": [],
            }

            with ui.stepper().classes("w-full") as stepper:
                with ui.step("Login"):
                    ui.label("Authenticate with Gradescope").classes(
                        "text-lg font-semibold mb-2"
                    )
                    email = ui.input(
                        "Email", placeholder="your-email@university.edu"
                    ).classes("w-full")
                    password = ui.input(
                        "Password", password=True, password_toggle_button=True
                    ).classes("w-full")

                    async def do_login() -> None:
                        try:
                            from gradescope_autograde.transport.session import GSSession

                            session = GSSession()
                            success = session.login(email.value, password.value)
                            if success:
                                state["logged_in"] = True
                                state["email"] = email.value
                                state["password"] = password.value
                                state["session"] = session
                                from gradescope_autograde.client.client import GSClient

                                client = GSClient(session)
                                courses = client.list_courses()
                                state["courses"] = courses
                                course_select.options = {
                                    c.get("id", c.get("name", "")): c.get(
                                        "name", c.get("short_name", "")
                                    )
                                    for c in courses
                                }
                                course_select.update()
                                ui.notify("Login successful!", type="positive")
                                stepper.next()
                            else:
                                ui.notify(
                                    "Login failed. Check credentials.",
                                    type="negative",
                                )
                        except Exception as e:
                            ui.notify(f"Error: {e}", type="negative")

                    ui.button("Login & Fetch Courses", on_click=do_login).classes(
                        "mt-4"
                    )

                with ui.step("Select Assignment"):
                    ui.label("Choose Course and Assignment").classes(
                        "text-lg font-semibold mb-2"
                    )

                    course_select = ui.select(
                        label="Course",
                        options={},
                        on_change=lambda e: state.update(course_id=e.value),
                    ).classes("w-full mb-4")

                    assign_select = ui.select(
                        label="Assignment",
                        options={},
                        on_change=lambda e: state.update(assignment_id=e.value),
                    ).classes("w-full mb-4")

                    async def fetch_assignments() -> None:
                        if not state["course_id"]:
                            ui.notify("Select a course first", type="warning")
                            return
                        try:
                            from gradescope_autograde.client.client import GSClient
                            from gradescope_autograde.transport.session import GSSession

                            session = state.get("session") or GSSession()
                            if not state.get("logged_in"):
                                session.login(state["email"], state["password"])
                            client = GSClient(session)
                            assignments = client.list_assignments(state["course_id"])
                            state["assignments"] = assignments
                            if not assignments:
                                ui.notify("No assignments found for this course.", type="warning")
                            assign_select.options = {
                                a.get("id", ""): a.get("title", a.get("name", ""))
                                for a in assignments
                            }
                            assign_select.update()
                        except Exception as e:
                            ui.notify(f"Error: {e}", type="negative")

                    ui.button("Fetch Assignments", on_click=fetch_assignments).classes(
                        "mb-4"
                    )
                    ui.button("Next", on_click=lambda: stepper.next()).classes("mt-2")

                with ui.step("Configure"):
                    ui.label("Grading Configuration").classes(
                        "text-lg font-semibold mb-2"
                    )

                    ui.upload(
                        label="Question & Answer PDF",
                        on_upload=lambda e: state.update(question_pdf=e.content),
                    ).classes("w-full mb-4")

                    def _on_rubric_upload(e):
                        import tempfile
                        from pathlib import Path
                        from gradescope_autograde.grader.rubric_parser import load_rubric

                        suffix = Path(e.name).suffix.lower()
                        if suffix in (".yaml", ".yml"):
                            import yaml
                            state["rubric_yaml"] = e.content
                            state["rubric_data"] = yaml.safe_load(e.content.decode("utf-8"))
                        elif suffix in (".pdf", ".tex"):
                            tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
                            tmp.write(e.content)
                            tmp.close()
                            state["rubric_data"] = load_rubric(tmp.name)
                            Path(tmp.name).unlink(missing_ok=True)
                        else:
                            ui.notify(f"Unsupported rubric format: {suffix}", type="warning")

                    ui.upload(
                        label="Rubric File (.yaml / .yml / .pdf / .tex)",
                        on_upload=_on_rubric_upload,
                    ).classes("w-full mb-4")

                    ui.label("Extra Grading Instructions:")
                    extra_instructions = ui.textarea(
                        placeholder="Add any special grading instructions here..."
                    ).classes("w-full mb-4")

                    ui.label("Questions (comma-separated IDs, e.g. q1,q3):")
                    question_ids_input = ui.input(
                        placeholder="Leave empty to grade all questions"
                    ).classes("w-full mb-4")

                    ui.label("AI Model:")
                    with ui.row():
                        ui.select(
                            label="Provider",
                            options={
                                "opencode-go": "OpenCode Go",
                                "lmstudio": "LM Studio (Local)",
                            },
                            value="opencode-go",
                            on_change=lambda e: state.update(
                                selected_provider=e.value
                            ),
                        )
                        ui.select(
                            label="Model",
                            options={
                                "deepseek-v4-flash": "DeepSeek V4 Flash",
                                "mimo-v2.5": "MiMo V2.5 (Multimodal)",
                            },
                            value="deepseek-v4-flash",
                            on_change=lambda e: state.update(
                                selected_model=e.value
                            ),
                        )

                    verbose_checkbox = ui.checkbox("Verbose errors (show full traceback)")
                    state["verbose"] = False
                    verbose_checkbox.on("change", lambda e: state.update(verbose=e.args))

                    upload_checkbox = ui.checkbox("Upload grades to Gradescope (DANGER!)")
                    state["upload"] = False
                    upload_checkbox.on("change", lambda e: state.update(upload=e.args))

                    pages_checkbox = ui.checkbox("Add [Page N of M] markers for unmapped PDFs")
                    state["with_pages"] = False
                    pages_checkbox.on("change", lambda e: state.update(with_pages=e.args))

                    ui.label("PDF Text Extraction:")
                    extraction_select = ui.select(
                        label="Extraction mode",
                        options={
                            "auto": "Auto (OCR for text models, images for multimodal)",
                            "ocr": "OCR only (tesseract, works with all models)",
                            "multimodal": "Multimodal (send images to LLM, requires mimo-v2.5)",
                        },
                        value="auto",
                        on_change=lambda e: state.update(extraction=e.value),
                    ).classes("w-full mb-4")

                    ui.button("Next", on_click=lambda: stepper.next()).classes("mt-4")

                with ui.step("Grade"):
                    ui.label("Grading Progress").classes("text-lg font-semibold mb-2")

                    result_container = ui.column().classes("w-full")
                    progress = ui.linear_progress(show_value=False).classes(
                        "w-full mb-4"
                    )
                    log_output = ui.log().classes("w-full h-64")

                    async def run_grading() -> None:
                        progress.value = 0
                        log_output.push("Starting grading pipeline...")
                        try:
                            from gradescope_autograde.config import load_config
                            from gradescope_autograde.transport.session import GSSession
                            from gradescope_autograde.client.client import GSClient
                            from gradescope_autograde.grader.engine import GradingEngine
                            from gradescope_autograde.grader.review import ReviewQueue
                            from gradescope_autograde.grader.providers.lmstudio import (
                                LMStudioProvider,
                            )
                            from gradescope_autograde.grader.providers.opencode_go import (
                                OpenCodeGoProvider,
                            )
                            from gradescope_autograde.workflow.pipeline import Pipeline

                            config = load_config(config_path)
                            session = state.get("session") or GSSession()
                            if not state.get("logged_in"):
                                session.login(state["email"], state["password"])
                            client = GSClient(session)

                            if state["selected_provider"] == "lmstudio":
                                provider = LMStudioProvider(model=state["selected_model"])
                            else:
                                provider = OpenCodeGoProvider(
                                    model=state["selected_model"],
                                    api_key=config.llm.api_key or None,
                                )
                            engine = GradingEngine(provider)
                            review_queue = ReviewQueue(
                                threshold=config.workflow.review_threshold
                            )
                            pipeline_obj = Pipeline(client, engine, review_queue)

                            rubric = state.get("rubric_data") or {"questions": []}
                            extra = extra_instructions.value.strip()
                            if extra and rubric.get("questions"):
                                for q in rubric["questions"]:
                                    existing = q.get("extra_instructions", "") or ""
                                    q["extra_instructions"] = (
                                        f"{existing}\n{extra}".strip()
                                    )

                            log_output.push(
                                f"Fetching submissions for assignment "
                                f"{state['assignment_id']}..."
                            )
                            progress.value = 0.1

                            q_ids_raw = question_ids_input.value.strip()
                            q_ids = [x.strip() for x in q_ids_raw.split(",") if x.strip()] if q_ids_raw else None
                            result = pipeline_obj.run(
                                state["course_id"],
                                state["assignment_id"],
                                rubric,
                                dry_run=not state.get("upload", False),
                                question_ids=q_ids,
                                verbose=state.get("verbose", False),
                                upload=state.get("upload", False) or None,
                                with_pages=state.get("with_pages", False),
                                extraction=state.get("extraction", "auto"),
                            )

                            state["results"] = result.get("results", [])
                            progress.value = 1.0
                            log_output.push(
                                f"Grading complete! "
                                f"{result['summary']['completed']} submissions processed."
                            )
                            log_output.push(
                                f"Review queue: {result['review_count']} items "
                                f"need human review."
                            )

                            result_container.clear()
                            with result_container:
                                ui.label("Grading Complete").classes(
                                    "text-xl font-bold text-green-600"
                                )
                                ui.label(
                                    f"Processed: {result['summary']['completed']} | "
                                    f"Failed: {result['summary']['failed']} | "
                                    f"Review: {result['review_count']}"
                                )

                                columns = [
                                    {
                                        "name": "student",
                                        "label": "Student",
                                        "field": "student_name",
                                    },
                                    {
                                        "name": "question",
                                        "label": "Question",
                                        "field": "question_id",
                                    },
                                    {
                                        "name": "score",
                                        "label": "Score",
                                        "field": "score",
                                    },
                                    {
                                        "name": "confidence",
                                        "label": "Confidence",
                                        "field": "confidence",
                                    },
                                ]
                                rows = state["results"][:20]
                                ui.table(columns=columns, rows=rows).classes(
                                    "w-full mt-4"
                                )

                            ui.notify("Grading complete!", type="positive")
                        except Exception as e:
                            log_output.push(f"Error: {e}")
                            ui.notify(f"Grading failed: {e}", type="negative")

                    ui.button(
                        "Start Grading (Dry Run)", on_click=run_grading
                    ).classes("mt-4")

                with ui.step("Export"):
                    ui.label("Export Results").classes("text-lg font-semibold mb-2")
                    ui.label(
                        "Grading is complete. Choose export format:"
                    ).classes("mb-4")

                    async def export_csv() -> None:
                        from gradescope_autograde.workflow.export import (
                            export_grades_csv,
                        )

                        path = export_grades_csv(
                            state["results"],
                            "data/output/grades/gradescope_upload.csv",
                            "gradescope",
                        )
                        ui.notify(f"Exported to {path}", type="positive")

                    async def export_detailed() -> None:
                        from gradescope_autograde.workflow.export import (
                            export_grades_csv,
                        )

                        path = export_grades_csv(
                            state["results"],
                            "data/output/grades/grades_detailed.csv",
                            "detailed",
                        )
                        ui.notify(f"Exported to {path}", type="positive")

                    async def export_json() -> None:
                        from gradescope_autograde.workflow.export import (
                            export_grades_csv,
                        )

                        path = export_grades_csv(
                            state["results"],
                            "data/output/grades/grades.json",
                            "json",
                        )
                        ui.notify(f"Exported to {path}", type="positive")

                    with ui.row():
                        ui.button("Export Gradescope CSV", on_click=export_csv)
                        ui.button("Export Detailed CSV", on_click=export_detailed)
                        ui.button("Export JSON", on_click=export_json)

    ui.run(host=host, port=port, title="Gradescope AutoGrade", reload=False)
