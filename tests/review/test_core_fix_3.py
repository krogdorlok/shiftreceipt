from conftest import S, V, YES
from diff import diff
from rules import evaluate, missing_answers


def test_uncountable_move_does_not_ask_questions_before_review():
    events = diff(
        V(1, [S("2026-10-19", "12:00", "17:00", "   ")]),
        V(2, [S("2026-10-19", "12:00", "17:00", "Location A")]),
    )

    assert evaluate(events, {}, YES, 2000)[0].status == "needs_review"
    assert missing_answers(events, {}) == []
