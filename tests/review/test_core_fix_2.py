from conftest import NO_ANS, S, V, YES
from diff import diff
from rules import evaluate, total


def test_multiple_equal_length_moves_are_not_guessed_by_list_order():
    previous = [
        S("2026-10-19", "12:00", "17:00", "Location A"),
        S("2026-10-20", "12:00", "17:00", "Location B"),
    ]
    current = [
        S("2026-10-21", "12:00", "17:00", "Location B"),
        S("2026-10-22", "12:00", "17:00", "Location A"),
    ]
    events = diff(V(1, previous), V(2, current))
    lines = evaluate(events, {e.id: NO_ANS for e in events}, YES, 2000)

    assert total(lines) == 0
    assert all(line.status == "needs_review" for line in lines)
