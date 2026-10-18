"""A completed rest-premium shift should become claimable later that same day."""
from datetime import datetime

import agent
import db
from conftest import S
from extract import schedule_text
from test_flow import A, SETUP, say  # noqa: F401


def test_rest_premium_due_after_shift_ends_on_its_day(A, monkeypatch):
    for text in ("\n".join(SETUP), schedule_text([
        S("2026-10-23", "16:00", "23:00"),
        S("2026-10-24", "07:00", "15:00"),
    ]), "GOT 2026-10-03", "CONFIRM"):
        say(A, "worker", text)

    class AfterShift(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 24, 20, 0, tzinfo=tz)

    monkeypatch.setattr(agent, "datetime", AfterShift)
    response = say(A, "worker", "RECEIPT")
    profile, _ = db.get_profile(A.DB_PATH, "worker")
    assert "Notice preview" in response
    assert any(line["rule"] == "R6" for line in profile["notice"]["lines"])
