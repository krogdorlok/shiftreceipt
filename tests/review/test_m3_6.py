"""Duplicate images should be recognized even before onboarding is complete."""
import agent
import db


def test_duplicate_image_during_onboarding_is_acknowledged_as_duplicate(tmp_path, monkeypatch):
    path = str(tmp_path / "duplicate.db")
    db.init(path)
    monkeypatch.setattr(agent, "DB_PATH", path)
    agent.PENDING_IMAGES.clear()

    first = agent.handle_image("worker", b"same image", "image/png")
    second = agent.handle_image("worker", b"same image", "image/png")

    assert "once you are set up" in first[0]
    assert second == ["Already have this one."]
