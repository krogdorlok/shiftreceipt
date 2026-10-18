from conftest import NO_ANS, S, V, YES
from diff import diff
from rules import evaluate, total


def test_move_out_of_two_shift_day_does_not_pay_as_new_shift():
    previous = [
        S("2026-10-19", "09:00", "12:00", "Location A"),
        S("2026-10-19", "14:00", "18:00", "Location A"),
    ]
    current = [
        S("2026-10-19", "09:00", "12:00", "Location A"),
        S("2026-10-20", "14:00", "18:00", "Location B"),
    ]

    events = diff(V(1, previous), V(2, current))
    lines = evaluate(events, {e.id: NO_ANS for e in events}, YES, 2000)

    assert total(lines) == 0
    assert all(line.status == "needs_review" for line in lines)
