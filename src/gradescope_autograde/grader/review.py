from __future__ import annotations


class ReviewQueue:

    def __init__(self, threshold: float = 0.7) -> None:
        self.threshold = threshold
        self._items: list[dict] = []

    def check(self, submission_id: str, result: dict) -> dict | None:
        needs_review = False
        reason = ""

        if result["confidence"] < self.threshold:
            needs_review = True
            reason = "low_confidence"
        elif "needs_review" in result.get("flags", []):
            needs_review = True
            reason = "flagged"

        if needs_review:
            item = {
                "submission_id": submission_id,
                "question_id": result["question_id"],
                "score": result["score"],
                "confidence": result["confidence"],
                "feedback": result["feedback"],
                "reason": reason,
                "status": "pending",
            }
            self._items.append(item)
            return item
        return None

    @property
    def pending(self) -> list[dict]:
        return [item for item in self._items if item["status"] == "pending"]

    @property
    def count(self) -> int:
        return len(self.pending)

    def approve(self, index: int) -> None:
        if 0 <= index < len(self._items):
            self._items[index]["status"] = "approved"

    def reject(self, index: int, notes: str = "") -> None:
        if 0 <= index < len(self._items):
            self._items[index]["status"] = "rejected"
            self._items[index]["reviewer_notes"] = notes
