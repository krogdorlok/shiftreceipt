import re

import notice
from test_flow import A, golden, say  # noqa: F401


def test_changing_manager_invalidates_old_notice_preview(A, monkeypatch):
    preview = golden(A, "worker")[-1]
    nid = re.search(r"reply SEND (\d+)", preview)[1]
    sent_to = []
    monkeypatch.setattr(notice, "send", lambda to, pdf, name: sent_to.append(to) or "<message>")
    say(A, "worker", "MANAGER new@example.com")
    response = say(A, "worker", f"SEND {nid}")
    assert sent_to == [] and "not pending" in response
