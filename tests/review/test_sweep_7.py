"""A manager estimate must not leave a worker notice based on the old rate sendable."""
import re

import notice
from conftest import S
from extract import schedule_text
from test_flow import A, SETUP, golden, say  # noqa: F401


def test_manager_rate_change_invalidates_worker_notice(A, monkeypatch):
    preview = golden(A, "worker")[-1]
    nid = re.search(r"reply SEND (\d+)", preview)[1]
    sent = []
    monkeypatch.setattr(notice, "render_notice", lambda *args: b"%PDF-1.4")
    monkeypatch.setattr(notice, "send", lambda to, pdf, name: sent.append(to) or "<message>")

    say(A, "worker", "MODE manager")
    say(A, "worker", "RATE 30")
    say(A, "worker", "MODE worker")
    say(A, "worker", f"SEND {nid}")

    assert sent == [], "the $20/h preview must be invalid after RATE changes to $30/h"


def test_overtime_change_invalidates_rest_notice(A, monkeypatch):
    for text in ("\n".join(SETUP), schedule_text([
        S("2026-10-16", "16:00", "23:00"), S("2026-10-17", "07:00", "15:00"),
    ]), "GOT 2026-10-03"):
        say(A, "worker", text)
    preview = say(A, "worker", "CONFIRM")
    nid = re.search(r"reply SEND (\d+)", preview)[1]
    sent = []
    monkeypatch.setattr(notice, "render_notice", lambda *args: b"%PDF-1.4")
    monkeypatch.setattr(notice, "send", lambda to, pdf, name: sent.append(to) or "<message>")

    say(A, "worker", "OT 2026-10-17 120")
    say(A, "worker", f"SEND {nid}")

    assert sent == [], "the $80 rest preview must be invalid after OT lowers it to $60"
