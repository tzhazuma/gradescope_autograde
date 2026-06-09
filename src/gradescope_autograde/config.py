"""Configuration loader with YAML parsing and environment variable interpolation."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _load_dotenv(path: str = ".env") -> None:
    """Load variables from a .env file into the environment if present."""
    env_path = Path(path)
    if not env_path.exists():
        return
    with env_path.open() as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip("\"'")
            if key and not os.environ.get(key):
                os.environ[key] = val

import yaml


@dataclass
class AuthConfig:
    email: str = ""
    password: str = ""
    cookie: str = ""


@dataclass
class GradescopeConfig:
    base_url: str = "https://www.gradescope.com"
    course_id: str | None = None
    request_delay: float = 1.0
    max_retries: int = 3


@dataclass
class LLMConfig:
    provider: str = "opencode-go"
    model: str = "deepseek-v4-flash"
    multimodal_model: str = "mimo-v2.5"
    api_key: str = ""
    base_url: str = "https://opencode.ai/zen/go/v1"
    temperature: float = 0.1
    max_tokens: int = 4096


@dataclass
class LMStudioConfig:
    base_url: str = "http://localhost:1234/v1"
    auto_discover: bool = True
    default_model: str = ""


@dataclass
class PDFInputConfig:
    path: str = ""
    question_separator: str = "## Question"


@dataclass
class RubricConfig:
    path: str = "config/rubrics/"
    default_rubric: str = "default_rubric.yaml"


@dataclass
class WorkflowConfig:
    auto_upload: bool = False
    review_threshold: float = 0.7
    batch_size: int = 50


@dataclass
class OutputConfig:
    grades_dir: str = "data/output/grades/"
    format: str = "gradescope_csv"
    generate_feedback: bool = True


@dataclass
class AppConfig:
    auth: AuthConfig = field(default_factory=AuthConfig)
    gradescope: GradescopeConfig = field(default_factory=GradescopeConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    lmstudio: LMStudioConfig = field(default_factory=LMStudioConfig)
    pdf_input: PDFInputConfig = field(default_factory=PDFInputConfig)
    rubric: RubricConfig = field(default_factory=RubricConfig)
    workflow: WorkflowConfig = field(default_factory=WorkflowConfig)
    output: OutputConfig = field(default_factory=OutputConfig)


def _interpolate_env(value: Any) -> Any:
    """Recursively interpolate ${VAR} references in string values."""
    if isinstance(value, str):
        return os.path.expandvars(value)
    if isinstance(value, dict):
        return {k: _interpolate_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate_env(item) for item in value]
    return value


def _build_dataclass(cls: type, data: dict[str, Any]) -> Any:
    """Construct a dataclass from a dict, ignoring unknown keys."""
    import dataclasses

    field_names = {f.name for f in dataclasses.fields(cls)}
    filtered = {k: v for k, v in data.items() if k in field_names}
    return cls(**filtered)


def load_config(path: str = "config/config.yaml") -> AppConfig:
    """Load and parse YAML config with env var interpolation.

    Resolution order:
        1. Load ``.env`` file if present (without overwriting existing env vars).
        2. Try *path* as-is.
        3. Fall back to ``path`` with ``.yaml`` → ``.example.yaml``.
        4. Raise FileNotFoundError if neither exists.
    """
    _load_dotenv(".env")
    config_path = Path(path)

    if not config_path.exists():
        example_path = config_path.with_name(
            config_path.stem.replace(".yaml", "") + ".example.yaml"
        )
        if example_path.exists():
            config_path = example_path
        else:
            raise FileNotFoundError(
                f"Config not found: {path} (also tried {example_path})"
            )

    with open(config_path, "r", encoding="utf-8") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh) or {}

    data = _interpolate_env(raw)

    return AppConfig(
        auth=_build_dataclass(AuthConfig, data.get("auth", {})),
        gradescope=_build_dataclass(GradescopeConfig, data.get("gradescope", {})),
        llm=_build_dataclass(LLMConfig, data.get("llm", {})),
        lmstudio=_build_dataclass(LMStudioConfig, data.get("lmstudio", {})),
        pdf_input=_build_dataclass(PDFInputConfig, data.get("pdf_input", {})),
        rubric=_build_dataclass(RubricConfig, data.get("rubric", {})),
        workflow=_build_dataclass(WorkflowConfig, data.get("workflow", {})),
        output=_build_dataclass(OutputConfig, data.get("output", {})),
    )
