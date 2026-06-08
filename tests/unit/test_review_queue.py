from gradescope_autograde.grader.review import ReviewQueue


def test_review_queue_below_threshold():
    rq = ReviewQueue(threshold=0.7)
    result = {"question_id": "q1", "score": 5, "confidence": 0.5, "feedback": "", "flags": []}
    item = rq.check("sub_1", result)
    assert item is not None
    assert item["reason"] == "low_confidence"
    assert rq.count == 1

def test_review_queue_above_threshold():
    rq = ReviewQueue(threshold=0.7)
    result = {"question_id": "q1", "score": 5, "confidence": 0.9, "feedback": "", "flags": []}
    item = rq.check("sub_1", result)
    assert item is None
    assert rq.count == 0

def test_review_queue_flagged():
    rq = ReviewQueue(threshold=0.7)
    result = {
        "question_id": "q1", "score": 5, "confidence": 0.9,
        "feedback": "", "flags": ["needs_review"],
    }
    item = rq.check("sub_1", result)
    assert item is not None
    assert item["reason"] == "flagged"

def test_review_queue_approve_reject():
    rq = ReviewQueue(threshold=0.7)
    result = {"question_id": "q1", "score": 5, "confidence": 0.5, "feedback": "", "flags": []}
    rq.check("sub_1", result)
    assert rq.count == 1
    rq.approve(0)
    assert rq.count == 0
