import io
import re
import smtplib
from datetime import date

import pytest
from pypdf import PdfReader

import db
import notice
from test_flow import A, golden, say  # noqa: F401  (A is the agent fixture)

PROFILE = dict(name="Maria Lopez", employer="Big Retail Co", title="Cashier", manager="boss@example.com",
               store="Westwood, Los Angeles")
LINES = [dict(rule="R3", cents=2000, citation="OWS FWWO Rule 5", day="2026-10-20", change="shift moved"),
         dict(rule="R6", cents=8000, citation="OWS FWWO Rule 6", day="2026-10-24", change="under 10 hours rest")]


def fields(pdf: bytes) -> dict:
    return {k: v.get("/V") for k, v in PdfReader(io.BytesIO(pdf)).get_fields().items()}


def test_render_reads_back():
    f = fields(notice.render_notice(PROFILE, LINES, date(2026, 10, 18)))
    assert f["Employee"] == "Maria Lopez" and f["Employer"] == "Big Retail Co" and f["Date"] == "2026-10-18"
    assert "$100.00" in f[notice.F_DESC] and "2026-10-20" in f[notice.F_DATES]
    assert f["Predictability Pay"] == "/On" and f["Rest Between Shifts"] == "/On"
    assert f.get("Advance Notice of Work Schedule") in (None, "/Off")  # never alleged automatically
    assert f[notice.F_SIGN] == "Maria Lopez (typed)" and "Store manager, boss@example.com" == f[notice.F_WHO]


def test_render_missing_field_goes_to_description(monkeypatch):
    monkeypatch.setattr(notice, "F_EMPLOYEE", "No Such Field")
    f = fields(notice.render_notice(PROFILE, LINES[:1], date(2026, 10, 18)))
    assert "No Such Field: Maria Lopez." in f[notice.F_DESC] and f["Rest Between Shifts"] in (None, "/Off")


class FakeSMTP:
    sent, fail = [], False

    def __init__(self, host, port, timeout):
        assert (host, port, timeout) == ("smtp.gmail.com", 465, 20)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def login(self, user, password):
        if FakeSMTP.fail:
            raise smtplib.SMTPAuthenticationError(535, b"bad")

    def send_message(self, msg):
        FakeSMTP.sent.append(msg)


@pytest.fixture
def smtp(monkeypatch):
    monkeypatch.setenv("SMTP_USER", "agent@example.com")
    monkeypatch.setenv("SMTP_APP_PASSWORD", "secret-app-pw")
    FakeSMTP.sent, FakeSMTP.fail = [], False
    monkeypatch.setattr(notice.smtplib, "SMTP_SSL", FakeSMTP)
    return FakeSMTP


def test_send_builds_email(smtp):
    mid = notice.send("boss@example.com", b"%PDF-1.4", "Maria Lopez")
    m = smtp.sent[0]
    assert mid == m["Message-ID"] and m["To"] == "boss@example.com"
    assert m["Subject"] == "Notice to Cure under the LA Fair Work Week Ordinance - Maria Lopez"
    body = m.get_body().get_content()
    assert "15 calendar days from receipt" in body and "prepared with ShiftReceipt" in body
    assert [p.get_filename() for p in m.iter_attachments()] == ["Notice_to_Cure.pdf"]


def nid_of(text):
    return re.search(r"reply SEND (\d+)", text)[1]


def test_send_flow_failure_retry_and_double_send(A, smtp):
    nid = nid_of(golden(A, "maria")[-1])
    smtp.fail = True
    r = say(A, "maria", f"SEND {nid}")
    assert r == f"Not sent. Try SEND {nid} again." and smtp.sent == []
    smtp.fail = False
    r = say(A, "maria", f"SEND {nid}")
    assert r.startswith("Sent") and "15 calendar days from receiving it" in r and "secret-app-pw" not in r
    assert len(smtp.sent) == 1
    pdf = smtp.sent[0].get_payload()[1].get_content()
    assert "$70.00" in fields(pdf)[notice.F_DESC]  # rest premium not claimed before the shift is worked
    assert "not pending" in say(A, "maria", f"SEND {nid}") and len(smtp.sent) == 1


def test_other_sender_cannot_send(A, smtp):
    nid = nid_of(golden(A, "maria")[-1])
    golden(A, "bob", upto=7)
    assert "not pending" in say(A, "bob", f"SEND {nid}") and smtp.sent == []
    assert "not pending" in say(A, "maria", "SEND 999") and smtp.sent == []


def test_send_falls_back_to_587_when_465_blocked(monkeypatch, smtp):
    def blocked(*a, **k):
        raise TimeoutError()
    used = []

    class Plain(FakeSMTP):
        def __init__(self, host, port, timeout):
            used.append(port)

        def starttls(self):
            pass

    monkeypatch.setattr(notice.smtplib, "SMTP_SSL", blocked)
    monkeypatch.setattr(notice.smtplib, "SMTP", Plain)
    assert notice.send("boss@example.com", b"%PDF", "Maria Lopez") and used == [587] and len(smtp.sent) == 1


def test_send_auth_error_is_not_retried_on_587(monkeypatch, smtp):
    smtp.fail = True
    monkeypatch.setattr(notice.smtplib, "SMTP", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no retry")))
    with pytest.raises(smtplib.SMTPAuthenticationError):
        notice.send("boss@example.com", b"%PDF", "Maria Lopez")


def test_send_over_https_when_resend_key_set(monkeypatch):
    import httpx
    seen = {}

    def post(url, headers, timeout, json):
        seen.update(url=url, auth=headers["Authorization"], json=json)
        return httpx.Response(200, json={"id": "re_123"}, request=httpx.Request("POST", url))
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setattr(notice.httpx, "post", post)
    monkeypatch.setattr(notice.smtplib, "SMTP_SSL", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no smtp")))
    assert notice.send("boss@example.com", b"%PDF", "Maria Lopez") == "re_123"
    assert seen["url"] == "https://api.resend.com/emails" and seen["auth"] == "Bearer re_test"
    assert seen["json"]["to"] == ["boss@example.com"] and seen["json"]["attachments"][0]["filename"] == "Notice_to_Cure.pdf"
    assert "15 calendar days from receipt" in seen["json"]["text"]


def test_https_error_raises(monkeypatch):
    import httpx
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setattr(notice.httpx, "post", lambda url, **k: httpx.Response(403, request=httpx.Request("POST", url)))
    with pytest.raises(httpx.HTTPStatusError):
        notice.send("boss@example.com", b"%PDF", "Maria Lopez")
