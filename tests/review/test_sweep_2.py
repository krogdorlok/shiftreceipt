from conftest import NO_ANS, S, V, YES
from diff import diff
from rules import evaluate


def test_daylight_saving_cancelled_shift_uses_elapsed_hours():
    for day, learned, expected_cents in (
        ("2026-11-01", "2026-10-30T09:00", 5000),  # clocks fall back: five elapsed hours
        ("2026-03-08", "2026-03-01T09:00", 3000),  # clocks spring forward: three elapsed hours
    ):
        events = diff(V(1, [S(day, "00:00", "04:00")]), V(2, [], learned))
        lines = evaluate(events, {e.id: NO_ANS for e in events}, YES, 2000)
        assert lines[0].cents == expected_cents
