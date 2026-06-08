"""Textual TUI for Gradescope AutoGrade."""

from gradescope_autograde.tui.app import GradescopeTUI


def run_tui() -> None:
    """Launch the interactive Textual TUI."""
    app = GradescopeTUI()
    app.run()


__all__ = ["GradescopeTUI", "run_tui"]
