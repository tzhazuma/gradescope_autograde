from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.widgets import Label, Select, Static


class ModelSelector(Select[str]):
    def __init__(self, **kwargs) -> None:
        if "id" not in kwargs:
            kwargs["id"] = "model-select"
        super().__init__(
            options=[("Loading models...", "__loading__")],
            prompt="Select an LLM model",
            **kwargs,
        )
        self._models: list[dict] = []

    def on_mount(self) -> None:
        self._discover_models()

    @work(exclusive=True, thread=True)
    def _discover_models(self) -> None:
        try:
            from gradescope_autograde.grader.providers.lmstudio import LMStudioProvider
            from gradescope_autograde.grader.providers.opencode_go import OpenCodeGoProvider
            from gradescope_autograde.grader.providers.registry import ModelRegistry

            registry = ModelRegistry()
            registry.register("opencode-go", OpenCodeGoProvider())
            registry.register("lmstudio", LMStudioProvider())
            models = registry.discover_all()
            self.app.call_from_thread(self._populate_models, models)
        except Exception:
            self.app.call_from_thread(
                self._populate_models,
                [
                    {
                        "provider": "opencode-go",
                        "id": "deepseek-v4-flash",
                        "name": "DeepSeek V4 Flash",
                    },
                    {
                        "provider": "opencode-go",
                        "id": "mimo-v2.5",
                        "name": "MiMo V2.5",
                    },
                ],
            )

    def _populate_models(self, models: list[dict]) -> None:
        self._models = models
        options = []
        for m in models:
            provider = m.get("provider", "?")
            model_id = m.get("id", "?")
            name = m.get("name", model_id)
            if model_id == "__error__":
                options.append((f"[dim]{provider}: unreachable[/]", "__skip__"))
            else:
                options.append((f"{provider}::{model_id}  ({name})", f"{provider}::{model_id}"))

        if not options:
            options = [("No models found", "__skip__")]

        self.set_options(options)
        if options and options[0][1] not in ("__skip__", "__loading__"):
            self.value = options[0][1]

    @property
    def selected_model(self) -> tuple[str, str] | None:
        value = self.value
        if value in (Select.BLANK, "__skip__", "__loading__", None):
            return None
        if "::" in value:
            provider, model_id = value.split("::", 1)
            return provider, model_id
        return None
