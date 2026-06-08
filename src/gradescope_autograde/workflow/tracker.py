"""Persistent progress tracker — survives crashes for resume support."""

from __future__ import annotations

import json
from pathlib import Path


class ProgressTracker:
    """Tracks which submissions have been graded, persisted to a state file.

    Enables resuming an interrupted grading run without re-processing
    already-completed submissions.

    Args:
        state_file: Path to the JSON state file on disk.
    """

    def __init__(self, state_file: str = ".grading_state.json") -> None:
        self.state_file = Path(state_file)
        self.state: dict = self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> dict:
        """Load state from disk, or return default if file doesn't exist."""
        if self.state_file.exists():
            return json.loads(self.state_file.read_text())
        return {"completed_ids": [], "last_index": 0, "total": 0}

    def save(self) -> None:
        """Write current state to disk."""
        self.state_file.write_text(json.dumps(self.state, indent=2))

    # ------------------------------------------------------------------
    # Tracking
    # ------------------------------------------------------------------

    def mark_complete(self, submission_id: str) -> None:
        """Record a submission as fully processed.

        Args:
            submission_id: The Gradescope submission identifier.
        """
        if submission_id not in self.state["completed_ids"]:
            self.state["completed_ids"].append(submission_id)
        self.save()

    def is_complete(self, submission_id: str) -> bool:
        """Check whether a submission has already been processed.

        Args:
            submission_id: The Gradescope submission identifier.

        Returns:
            ``True`` if this submission was previously marked complete.
        """
        return submission_id in self.state["completed_ids"]

    def set_total(self, total: int) -> None:
        """Set the expected total number of submissions.

        Args:
            total: Total submission count for the current run.
        """
        self.state["total"] = total
        self.save()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def completed_count(self) -> int:
        """Number of submissions marked complete."""
        return len(self.state["completed_ids"])

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Clear all tracked progress and delete the state file contents."""
        self.state = {"completed_ids": [], "last_index": 0, "total": 0}
        self.save()
