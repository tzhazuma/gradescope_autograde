from __future__ import annotations

from nicegui import ui


def run_gui(host: str = "127.0.0.1", port: int = 8080) -> None:
    """Launch the NiceGUI web interface for Gradescope AutoGrade."""

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
                "extra_instructions": "",
                "selected_model": "deepseek-v4-flash",
                "selected_provider": "opencode-go",
                "logged_in": False,
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
                            from gradescope_autograde.config import load_config
                            from gradescope_autograde.client.client import GSClient
                            from gradescope_autograde.transport.session import GSSession

                            config = load_config()
                            session = GSSession()
                            session.login(config.auth.email, config.auth.password)
                            client = GSClient(session)
                            assignments = client.list_assignments(state["course_id"])
                            state["assignments"] = assignments
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

                    ui.upload(
                        label="Rubric YAML",
                        on_upload=lambda e: state.update(rubric_yaml=e.content),
                    ).classes("w-full mb-4")

                    ui.label("Extra Grading Instructions:")
                    extra_instructions = ui.textarea(
                        placeholder="Add any special grading instructions here..."
                    ).classes("w-full mb-4")

                    ui.label("AI Model:")
                    with ui.row():
                        ui.select(
                            label="Provider",
                            options={
                                "opencode-go": "OpenCode Go",
                                "lmstudio": "LM Studio (Local)",
                                "openai": "OpenAI",
                                "anthropic": "Anthropic",
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
                            from gradescope_autograde.grader.providers.opencode_go import (
                                OpenCodeGoProvider,
                            )
                            from gradescope_autograde.workflow.pipeline import Pipeline

                            config = load_config()
                            session = GSSession()
                            session.login(config.auth.email, config.auth.password)
                            client = GSClient(session)

                            provider = OpenCodeGoProvider(model=state["selected_model"])
                            engine = GradingEngine(provider)
                            review_queue = ReviewQueue(
                                threshold=config.workflow.review_threshold
                            )
                            pipeline_obj = Pipeline(client, engine, review_queue)

                            rubric: dict = {"questions": []}

                            log_output.push(
                                f"Fetching submissions for assignment "
                                f"{state['assignment_id']}..."
                            )
                            progress.value = 0.1

                            result = pipeline_obj.run(
                                state["course_id"],
                                state["assignment_id"],
                                rubric,
                                dry_run=True,
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
