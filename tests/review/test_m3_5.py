"""A schedule image received after NAME should survive a worker-flow restart."""
import agent
import db
from conftest import fixture


def test_image_during_onboarding_survives_restart(tmp_path, monkeypatch):
    path = str(tmp_path / "restart.db")
    db.init(path)
    monkeypatch.setattr(agent, "DB_PATH", path)
    agent.PENDING_IMAGES.clear()
    monkeypatch.setattr(agent, "extract", lambda data, mime, name, day: (fixture("v1"), []))

    agent.handle_text("worker", "NAME Maria Lopez")
    agent.handle_image("worker", b"schedule image", "image/png")
    agent.PENDING_IMAGES.clear()  # a new process has the same DB but no module memory
    reply = agent.handle_text("worker", "\n".join([
        "RATE 20", "EMPLOYER Big Retail Co", "TITLE Cashier", "STORE Westwood, Los Angeles",
        "MANAGER boss@example.com", "COVER yes yes yes",
    ]))

    assert "Tue Oct 20" in "\n".join(reply)
    assert len(db.versions(path, "worker", confirmed_only=False)) == 1
