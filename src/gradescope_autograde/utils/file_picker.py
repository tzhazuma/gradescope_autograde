"""Cross-platform file picker — opens native OS file dialog.

Platform support:
- macOS: AppleScript / osascript (built-in)
- Linux: zenity or kdialog (common on Ubuntu/Debian)
- Windows: PowerShell file dialog
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Literal


def _pick_macos(
    title: str,
    file_types: list[str] | None = None,
    directory: bool = False,
) -> str | None:
    """macOS file picker via AppleScript."""
    if directory:
        script = f'choose folder with prompt "{title}"'
    else:
        script = f'choose file with prompt "{title}"'
    
    cmd = [
        "osascript",
        "-e",
        f'set theFile to {script}',
        "-e",
        "set thePath to POSIX path of theFile",
        "-e",
        "return thePath",
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            path = result.stdout.strip()
            return path if path else None
        if result.stderr:
            import sys
            print(f"[file_picker] osascript error: {result.stderr.strip()}", file=sys.stderr)
    except subprocess.TimeoutExpired:
        import sys
        print("[file_picker] osascript timed out", file=sys.stderr)
    except FileNotFoundError:
        import sys
        print("[file_picker] osascript not found on macOS", file=sys.stderr)
    except OSError as e:
        import sys
        print(f"[file_picker] osascript OS error: {e}", file=sys.stderr)
    return None


def _pick_linux(
    title: str,
    file_types: list[str] | None = None,
    directory: bool = False,
) -> str | None:
    """Linux file picker via zenity (preferred) or kdialog."""
    for tool in ("zenity", "kdialog"):
        if not _which(tool):
            continue
        try:
            if tool == "zenity":
                args = [tool, "--file-selection", f"--title={title}"]
                if directory:
                    args.append("--directory")
                if file_types:
                    # zenity uses --file-filter=NAME *.ext
                    patterns = " ".join(f"*.{t}" for t in file_types)
                    args.append(f"--file-filter=Supported {patterns}")
            else:  # kdialog
                args = [tool, "--getopenfilename", ".", title]
                if directory:
                    args = [tool, "--getexistingdirectory", "."]
            result = subprocess.run(
                args, capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                path = result.stdout.strip()
                if path:
                    return path
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            continue
    return None


def _pick_windows(
    title: str,
    file_types: list[str] | None = None,
    directory: bool = False,
) -> str | None:
    """Windows file picker via PowerShell."""
    ps_script = """
    Add-Type -AssemblyName System.Windows.Forms
    $dialog = New-Object System.Windows.Forms.OpenFileDialog
    $dialog.Title = "{title}"
    """
    if directory:
        ps_script = """
        Add-Type -AssemblyName System.Windows.Forms
        $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
        $dialog.Description = "{title}"
        """
    ps_script += """
    if ($dialog.ShowDialog() -eq 'OK') {
        Write-Output $dialog.FileName
    }
    """.format(title=title)
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            path = result.stdout.strip()
            return path if path else None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def _which(program: str) -> bool:
    """Check if a program is available on PATH."""
    try:
        return (
            subprocess.run(
                ["which", program], capture_output=True, timeout=5
            ).returncode
            == 0
        )
    except Exception:
        return False


def pick_file(
    title: str = "Select a file",
    file_types: list[str] | None = None,
    directory: bool = False,
) -> str | None:
    """Open native OS file picker dialog.

    Args:
        title: Dialog title.
        file_types: List of allowed extensions (e.g. ``["yaml", "yml"]``).
            ``None`` means all files.
        directory: If ``True``, pick a folder instead of a file.

    Returns:
        Absolute path string, or ``None`` if the user cancelled.
    """
    system = sys.platform
    if system == "darwin":
        return _pick_macos(title, file_types, directory)
    if system.startswith("linux") or system == "linux2":
        return _pick_linux(title, file_types, directory)
    if system == "win32":
        return _pick_windows(title, file_types, directory)
    return None
