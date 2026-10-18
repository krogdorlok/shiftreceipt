from conftest import S
from extract import schedule_text
from test_flow import A, SETUP, say  # noqa: F401


def test_corrected_schedule_can_later_reappear_as_new_version(A):
    say(A, "worker", "\n".join(SETUP))
    original = schedule_text([S("2026-10-20", "09:00", "17:00")])
    say(A, "worker", original)
    say(A, "worker", "EDIT 2026-10-20 10:00-18:00")
    say(A, "worker", "CONFIRM")
    response = say(A, "worker", original)
    assert "Here is what I read" in response
