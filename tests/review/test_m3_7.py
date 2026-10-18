"""Dropping the only shift from a later version must retain the cancellation."""
from datetime import date

import agent
import db
from conftest import S
from extract import schedule_text


def test_empty_confirmed_version_cancels_earlier_week(tmp_path, monkeypatch):
    path = str(tmp_path / "cancel.db")
    db.init(path)
    monkeypatch.setattr(agent, "DB_PATH", path)
    monkeypatch.setattr(agent, "_today", lambda: date(2026, 10, 18))
    agent.handle_text("worker", "\n".join([
        "NAME Maria Lopez", "RATE 20", "EMPLOYER Big Retail Co", "TITLE Cashier",
        "STORE Westwood, Los Angeles", "MANAGER boss@example.com", "COVER yes yes yes",
    ]))
    agent.handle_text("worker", schedule_text([S("2026-10-20", "09:00", "17:00")]))
    agent.handle_text("worker", "GOT 2026-10-03")
    agent.handle_text("worker", "CONFIRM")
    agent.handle_text("worker", schedule_text([S("2026-10-20", "10:00", "18:00")]))
    agent.handle_text("worker", "GOT 2026-10-17")
    agent.handle_text("worker", "DROP 2026-10-20")
    response = "\n".join(agent.handle_text("worker", "CONFIRM"))

    assert "shift cancelled" in response
    assert "Q1 " in response and "Q2 " in response
