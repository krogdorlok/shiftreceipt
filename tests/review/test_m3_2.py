"""A second upload must not strand an unconfirmed first version."""
import agent
import db
from conftest import fixture
from extract import schedule_text


def test_two_unconfirmed_uploads_can_both_be_confirmed(tmp_path, monkeypatch):
    path = str(tmp_path / "uploads.db")
    db.init(path)
    monkeypatch.setattr(agent, "DB_PATH", path)
    agent.handle_text("worker", "\n".join([
        "NAME Maria Lopez", "RATE 20", "EMPLOYER Big Retail Co", "TITLE Cashier",
        "STORE Westwood, Los Angeles", "MANAGER boss@example.com", "COVER yes yes yes",
    ]))
    agent.handle_text("worker", schedule_text(fixture("v1")))
    agent.handle_text("worker", schedule_text(fixture("v2")))
    agent.handle_text("worker", "CONFIRM")

    # The worker must be able to review and confirm the first saved schedule too.
    agent.handle_text("worker", schedule_text(fixture("v1")))
    agent.handle_text("worker", "CONFIRM")
    assert len(db.versions(path, "worker")) == 2
