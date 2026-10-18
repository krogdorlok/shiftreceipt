from conftest import NO_ANS, S, V, YES
from diff import diff
from rules import evaluate, total


def test_same_day_matching_does_not_guess_between_two_swapped_shifts():
    previous = [
        S("2026-10-19", "12:00", "17:00", "Location A"),
        S("2026-10-20", "09:00", "14:00", "Location B"),
    ]
    current = [
        S("2026-10-19", "09:00", "14:00", "Location B"),
        S("2026-10-20", "12:00", "17:00", "Location A"),
    ]
    events = diff(V(1, previous), V(2, current))
    lines = evaluate(events, {e.id: NO_ANS for e in events}, YES, 2000)

    assert total(lines) == 0
    assert all(line.status == "needs_review" for line in lines)
