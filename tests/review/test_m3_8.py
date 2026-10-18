"""The message size cap must not turn a partial rate into a valid smaller rate."""
import agent
import db


def test_oversize_paste_cannot_save_truncated_rate(tmp_path, monkeypatch):
    path = str(tmp_path / "rate.db")
    db.init(path)
    monkeypatch.setattr(agent, "DB_PATH", path)
    prefix = ("NAME " + "X" * 99 + "\n") * 18 + "NAME " + "X" * 97 + "\n"
    assert len(prefix) == 1993
    message = prefix + "RATE 200"
    assert len(message) == 2001

    agent.handle_text("worker", message)

    profile, _ = db.get_profile(path, "worker")
    assert "rate" not in profile
