"""A pasted prose line must not bypass the explicit SEND gate."""
import agent
import db


def test_multiline_prose_does_not_call_send_notice(tmp_path, monkeypatch):
    path = str(tmp_path / "send.db")
    db.init(path)
    monkeypatch.setattr(agent, "DB_PATH", path)
    agent.handle_text("worker", "\n".join([
        "NAME Maria Lopez", "RATE 20", "EMPLOYER Big Retail Co", "TITLE Cashier",
        "STORE Westwood, Los Angeles", "MANAGER boss@example.com", "COVER yes yes yes",
    ]))
    calls = []
    monkeypatch.setattr(agent, "send_notice", lambda sender, nid: calls.append((sender, nid)) or ["sent"])

    agent.handle_text("worker", "HELP\nDo not send receipt 7")

    assert calls == []
