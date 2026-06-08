import os
import platform
import shutil
import subprocess
import time
from pathlib import Path

import httpx

LMS_BINARY = "lms"
LMS_PATHS = {
    "Darwin": Path.home() / ".lmstudio" / "bin" / "lms",
    "Linux": Path.home() / ".lmstudio" / "bin" / "lms",
    "Windows": Path.home() / ".lmstudio" / "bin" / "lms.exe",
}
DEFAULT_PORT = 1234
HEALTH_URL = f"http://localhost:{DEFAULT_PORT}/v1/models"
STARTUP_TIMEOUT = 30


def detect_lmstudio() -> dict:
    """Detect LM Studio installation status.

    Returns dict with keys: installed, lms_path, server_running, desktop_installed
    """
    system = platform.system()
    lms_path = LMS_PATHS.get(system)

    # Check for lms binary
    has_lms = lms_path and lms_path.exists() if lms_path else False

    # Also check if lms is in PATH
    if not has_lms:
        lms_in_path = shutil.which(LMS_BINARY)
        if lms_in_path:
            has_lms = True
            lms_path = Path(lms_in_path)

    # Check if server is already running
    server_running = _check_server()

    # Check if desktop app exists (macOS .app bundle)
    desktop_installed = False
    if system == "Darwin":
        desktop_installed = Path("/Applications/LM Studio.app").exists()

    return {
        "installed": has_lms,
        "lms_path": str(lms_path) if lms_path else None,
        "server_running": server_running,
        "desktop_installed": desktop_installed,
        "platform": system,
    }


def get_install_instructions() -> str:
    """Return platform-specific install instructions."""
    system = platform.system()
    if system == "Darwin":
        return (
            "Install LM Studio:\n"
            "  1. Download from https://lmstudio.ai/\n"
            "  2. Open LM Studio.app once to initialize lms CLI\n"
            "  3. Or install headless: curl -fsSL https://lmstudio.ai/install.sh | bash"
        )
    elif system == "Linux":
        return (
            "Install LM Studio:\n"
            "  1. curl -fsSL https://lmstudio.ai/install.sh | bash\n"
            "  2. Or download AppImage from https://lmstudio.ai/"
        )
    else:
        return (
            "Install LM Studio:\n"
            "  1. Download from https://lmstudio.ai/\n"
            "  2. Run the installer\n"
            "  3. Or use: irm https://lmstudio.ai/install.ps1 | iex"
        )


def _check_server() -> bool:
    """Check if LM Studio server is running on default port."""
    try:
        resp = httpx.get(HEALTH_URL, timeout=3.0)
        return resp.status_code == 200
    except Exception:
        return False


class LmsManager:
    """Manage LM Studio server lifecycle via the lms CLI."""

    def __init__(self, port: int = DEFAULT_PORT, timeout: int = STARTUP_TIMEOUT):
        self.port = port
        self.timeout = timeout
        self._lms_path = self._find_lms()
        self._started_by_us = False

    def _find_lms(self) -> Path | None:
        system = platform.system()
        path = LMS_PATHS.get(system)
        if path and path.exists():
            return path
        which = shutil.which(LMS_BINARY)
        if which:
            return Path(which)
        return None

    @property
    def available(self) -> bool:
        return self._lms_path is not None

    def ensure_running(self) -> bool:
        """Ensure LM Studio server is running. Start it if not.

        Returns True if server is running (was already or started successfully).
        """
        if _check_server():
            return True

        if not self._lms_path:
            return False

        try:
            subprocess.Popen(
                [str(self._lms_path), "server", "start"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            self._started_by_us = True

            # Wait for server to be ready
            deadline = time.time() + self.timeout
            while time.time() < deadline:
                if _check_server():
                    return True
                time.sleep(1)

            return False
        except Exception:
            return False

    def stop(self) -> None:
        """Stop the server if we started it."""
        if not self._started_by_us or not self._lms_path:
            return

        try:
            subprocess.run(
                [str(self._lms_path), "server", "stop"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
            )
        except Exception:
            pass
        finally:
            self._started_by_us = False

    def status(self) -> dict:
        """Get current server status."""
        info = detect_lmstudio()
        info["lms_available"] = self.available
        info["port"] = self.port
        return info

    def __enter__(self):
        self.ensure_running()
        return self

    def __exit__(self, *args):
        self.stop()
