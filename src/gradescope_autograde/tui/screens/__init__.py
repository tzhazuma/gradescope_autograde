"""TUI screens for Gradescope AutoGrade."""

from gradescope_autograde.tui.screens.assignment_select import AssignmentSelectScreen
from gradescope_autograde.tui.screens.config_screen import ConfigScreen
from gradescope_autograde.tui.screens.course_select import CourseSelectScreen
from gradescope_autograde.tui.screens.grading_screen import GradingScreen
from gradescope_autograde.tui.screens.results_screen import ResultsScreen

__all__ = [
    "AssignmentSelectScreen",
    "ConfigScreen",
    "CourseSelectScreen",
    "GradingScreen",
    "ResultsScreen",
]
