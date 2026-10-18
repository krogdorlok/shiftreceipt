"""The 2,000-character parser limit also applies to pasted commands."""
import agent
import db


def test_multiline_input_cannot_bypass_parser_size_limit(tmp_path, monkeypatch):
    path = str(tmp_path / "long.db")
    db.init(path)
    monkeypatch.setattr(agent, "DB_PATH", path)
    text = ("NAME " + "x" * 100 + "\n") * 25 + "RATE 99"
    assert len(text) > 2000
    agent.handle_text("worker", text)
    data, _ = db.get_profile(path, "worker")
    assert "rate" not in data
