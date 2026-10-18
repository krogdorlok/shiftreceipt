from conftest import NO_ANS, S, V, YES
from diff import diff
from rules import evaluate, total


def test_blank_location_is_not_a_named_location_change():
    events = diff(
        V(1, [S("2026-10-19", "12:00", "17:00", "   ")]),
        V(2, [S("2026-10-19", "12:00", "17:00", "Location A")]),
    )
    lines = evaluate(events, {e.id: NO_ANS for e in events}, YES, 2000)

    assert total(lines) == 0
    assert lines[0].status == "needs_review"
