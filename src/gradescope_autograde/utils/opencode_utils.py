"""OpenCode CLI integration — install detection, config, and chat runner.

Provides helpers to:
- Detect whether ``opencode`` is installed and configured.
- Generate the ``opencode-go`` provider block for ``opencode.json``.
- Start an interactive chat session via ``opencode run``.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


def detect_opencode() -> dict:
    """Probe the system for an ``opencode`` installation.

    Returns a dict:
        installed: bool
        path: str | None (absolute path to the ``opencode`` binary)
        version: str | None (version string, e.g. ``"1.16.2"``)
        config_path: str | None (path to ``opencode.json``)
        has_provider: bool (whether an opencode-go provider is configured)
    """
    path = shutil.which("opencode")
    result: dict = {
        "installed": path is not None,
        "path": path,
        "version": None,
        "config_path": None,
        "has_provider": False,
    }
    if not path:
        return result

    try:
        r = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            result["version"] = r.stdout.strip().split("\n")[0]
    except Exception:
        pass

    config = Path.home() / ".config" / "opencode" / "opencode.json"
    if config.exists():
        result["config_path"] = str(config)
        try:
            data = json.loads(config.read_text())
            providers = data.get("provider", {})
            result["has_provider"] = "opencode-go" in providers or any(
                "opencode" in k.lower() for k in providers
            )
        except Exception:
            pass

    return result


def get_install_instructions() -> str:
    """Return cross-platform install instructions for OpenCode CLI."""
    return (
        "Install OpenCode CLI:\n\n"
        "macOS:\n"
        "  brew install opencode\n\n"
        "Linux:\n"
        "  curl -fsSL https://opencode.ai/install.sh | bash\n\n"
        "Windows:\n"
        "  irm https://opencode.ai/install.ps1 | iex\n\n"
        "After installation, run 'opencode --help' to verify."
    )


def generate_provider_config(api_key: str | None = None) -> str:
    """Generate the opencode-go provider JSON block for ``opencode.json``."""
    key = api_key or os.environ.get("OPENCODE_GO_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
    return json.dumps(
        {
            "name": "OpenCode Go",
            "env": ["OPENCODE_GO_API_KEY"],
            "models": {
                "deepseek-v4-flash": {
                    "name": "DeepSeek V4 Flash",
                    "limit": {"context": 1000000, "output": 128000},
                    "modalities": {"input": ["text"], "output": ["text"]},
                },
                "mimo-v2.5": {
                    "name": "MiMo V2.5",
                    "limit": {"context": 1000000, "output": 128000},
                    "modalities": {"input": ["text", "image"], "output": ["text"]},
                },
            },
        },
        indent=2,
    )


def merge_provider_to_config(provider_json_str: str) -> bool:
    """Add the opencode-go provider to the user's ``opencode.json``.

    Returns ``True`` on success.
    """
    config = Path.home() / ".config" / "opencode" / "opencode.json"
    if not config.exists():
        return False

    try:
        data = json.loads(config.read_text())
        if "provider" not in data:
            data["provider"] = {}
        provider = json.loads(provider_json_str)
        data["provider"]["opencode-go"] = provider
        bak = config.with_suffix(".json.bak.opencode-go")
        config.rename(bak)
        config.write_text(json.dumps(data, indent=2))
        return True
    except Exception:
        return False


def run_chat(message: str, working_dir: str | None = None) -> str:
    """Run ``opencode run <message>`` and return the output.

    Args:
        message: Natural-language command to send to opencode.
        working_dir: Optional working directory for the session.

    Returns:
        Stdout + stderr from the run command.
    """
    opencode = shutil.which("opencode")
    if not opencode:
        return "OpenCode is not installed. Run `brew install opencode` or visit https://opencode.ai"

    cmd = [opencode, "run", message]
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=working_dir,
        )
        return r.stdout + ("\n" + r.stderr if r.stderr else "")
    except subprocess.TimeoutExpired:
        return "OpenCode command timed out after 120 seconds."
    except Exception as e:
        return f"Error running opencode: {e}"
