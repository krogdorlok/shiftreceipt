"""Every image received during onboarding must survive until it can be confirmed."""
import agent
import db
from conftest import fixture


def test_two_images_before_onboarding_are_both_kept(tmp_path, monkeypatch):
    path = str(tmp_path / "images.db")
    db.init(path)
    monkeypatch.setattr(agent, "DB_PATH", path)
    agent.PENDING_IMAGES.clear()
    monkeypatch.setattr(agent, "extract", lambda data, mime, name, day:
                        (fixture("v1") if data == b"first" else fixture("v2"), []))

    agent.handle_text("worker", "NAME Maria Lopez")
    agent.handle_image("worker", b"first", "image/png")
    agent.handle_image("worker", b"second", "image/png")
    agent.handle_text("worker", "\n".join([
        "RATE 20", "EMPLOYER Big Retail Co", "TITLE Cashier", "STORE Westwood, Los Angeles",
        "MANAGER boss@example.com", "COVER yes yes yes",
    ]))

    assert len(db.versions(path, "worker", confirmed_only=False)) == 2
