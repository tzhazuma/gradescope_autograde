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


def generate_lmstudio_provider_config() -> str:
    """Generate the LM Studio provider JSON block for ``opencode.json``."""
    return json.dumps(
        {
            "name": "LM Studio",
            "env": [],
            "options": {
                "apiKey": "lm-studio",
                "baseURL": "http://localhost:1234/v1",
            },
            "models": {
                "gemma4-12b": {
                    "name": "Gemma 4 12B",
                    "limit": {"context": 131072, "output": 8192},
                    "modalities": {"input": ["text", "image"], "output": ["text"]},
                },
                "qwen3.5-9b": {
                    "name": "Qwen 3.5 9B",
                    "limit": {"context": 131072, "output": 8192},
                    "modalities": {"input": ["text"], "output": ["text"]},
                },
                "gemma4-e4b": {
                    "name": "Gemma 4 E4B",
                    "limit": {"context": 131072, "output": 8192},
                    "modalities": {"input": ["text", "image"], "output": ["text"]},
                },
                "qwen3.5-4b": {
                    "name": "Qwen 3.5 4B",
                    "limit": {"context": 131072, "output": 8192},
                    "modalities": {"input": ["text"], "output": ["text"]},
                },
            },
        },
        indent=2,
    )


def merge_provider_to_config(provider_json_str: str, provider_name: str = "opencode-go") -> bool:
    """Add a provider to the user's ``opencode.json``."""
    config = Path.home() / ".config" / "opencode" / "opencode.json"
    if not config.exists():
        return False
    try:
        data = json.loads(config.read_text())
        if "provider" not in data:
            data["provider"] = {}
        provider = json.loads(provider_json_str)
        data["provider"][provider_name] = provider
        bak = config.with_suffix(f".json.bak.{provider_name}")
        config.rename(bak)
        config.write_text(json.dumps(data, indent=2))
        return True
    except Exception:
        return False


def run_chat(message: str, working_dir: str | None = None, model: str = "opencode-go/mimo-v2.5", verbose: bool = False) -> str:
    """Run ``opencode run <message>`` and return the output.

    Args:
        message: Natural-language command to send to opencode.
        working_dir: Optional working directory for the session.
        model: Model identifier in ``provider/model`` format.
        verbose: If True, include stderr output.

    Returns:
        Stdout + stderr from the run command.
    """
    opencode = shutil.which("opencode")
    if not opencode:
        return "OpenCode is not installed. Run `brew install opencode` or visit https://opencode.ai"

    cmd = [opencode, "run", "-m", model, "--format", "json"] + message.strip().split()
    try:
        import json as _json
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=working_dir,
            bufsize=1,
        )
        
        response_parts = []
        full_output = []
        
        for line in process.stdout:
            line = line.strip()
            if not line:
                continue
            full_output.append(line)
            
            if verbose:
                import sys
                sys.stdout.write(line + "\n")
                sys.stdout.flush()
            
            try:
                event = _json.loads(line)
                event_type = event.get("type", "")
                
                if event_type == "text":
                    text = event.get("part", {}).get("text", "")
                    if text:
                        response_parts.append(text)
                elif event_type == "assistant":
                    content = event.get("part", {}).get("content", "")
                    if content:
                        response_parts.append(content)
                elif event_type == "step_end":
                    break
            except _json.JSONDecodeError:
                continue
        
        process.wait(timeout=30)
        
        if response_parts:
            return "".join(response_parts)
        
        if verbose:
            return "\n".join(full_output)
        
        return process.stdout.read() if process.stdout else ""
    except subprocess.TimeoutExpired:
        process.kill()
        return "OpenCode command timed out."
    except Exception as e:
        return f"Error running opencode: {e}"
