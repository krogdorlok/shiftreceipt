from conftest import S
from extract import schedule_text
from test_flow import A, SETUP, say  # noqa: F401


def test_next_week_schedule_is_not_change_to_previous_week(A):
    say(A, "worker", "\n".join(SETUP))
    say(A, "worker", schedule_text([S("2026-10-20", "09:00", "17:00")]))
    say(A, "worker", "GOT 2026-10-03")
    say(A, "worker", "CONFIRM")
    say(A, "worker", schedule_text([S("2026-10-27", "09:00", "17:00")]))
    say(A, "worker", "GOT 2026-10-17")
    response = say(A, "worker", "CONFIRM")
    assert "Q1" not in response
    assert "Estimated total: $0.00" in response
