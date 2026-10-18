"""Edge cases found by the Codex reviews (one test per bug that was fixed)."""
from uuid import uuid4
from datetime import date
from types import SimpleNamespace
import asyncio
from datetime import datetime
import json
from datetime import datetime, timedelta
import re

from conftest import NO_ANS, S, V, YES
from diff import diff
from rules import evaluate, total
from conftest import S, V, YES
from rules import evaluate, missing_answers
import pytest
from agent import DownloadError, download, image_url
from uagents_core.contrib.protocols.chat import Resource, ResourceContent
import httpx
from agent import MAX_BYTES, DownloadError, download
import extract
from google import genai
from google.genai import types
from uagents_core.contrib.protocols.chat import ChatMessage, StartSessionContent, TextContent
import agent
import db
from conftest import fixture
from extract import schedule_text
from conftest import S
from parser import parse
from test_flow import A, SETUP, say  # noqa: F401
from rules import evaluate
from models import LA
import notice
from test_flow import A, golden, say  # noqa: F401
from test_flow import A, SETUP, golden, say  # noqa: F401
from threading import Event
from test_flow import A, Ctx, SETUP, say  # noqa: F401
from uagents_core.contrib.protocols.chat import ChatMessage, TextContent


# from review test_core_fix_1
def test_blank_location_is_not_a_named_location_change():
    events = diff(
        V(1, [S("2026-10-19", "12:00", "17:00", "   ")]),
        V(2, [S("2026-10-19", "12:00", "17:00", "Location A")]),
    )
    lines = evaluate(events, {e.id: NO_ANS for e in events}, YES, 2000)

    assert total(lines) == 0
    assert lines[0].status == "needs_review"


# from review test_core_fix_2
def test_multiple_equal_length_moves_are_not_guessed_by_list_order():
    previous = [
        S("2026-10-19", "12:00", "17:00", "Location A"),
        S("2026-10-20", "12:00", "17:00", "Location B"),
    ]
    current = [
        S("2026-10-21", "12:00", "17:00", "Location B"),
        S("2026-10-22", "12:00", "17:00", "Location A"),
    ]
    events = diff(V(1, previous), V(2, current))
    lines = evaluate(events, {e.id: NO_ANS for e in events}, YES, 2000)

    assert total(lines) == 0
    assert all(line.status == "needs_review" for line in lines)


# from review test_core_fix_3
def test_uncountable_move_does_not_ask_questions_before_review():
    events = diff(
        V(1, [S("2026-10-19", "12:00", "17:00", "   ")]),
        V(2, [S("2026-10-19", "12:00", "17:00", "Location A")]),
    )

    assert evaluate(events, {}, YES, 2000)[0].status == "needs_review"
    assert missing_answers(events, {}) == []


# from review test_core_fix_4
def test_same_day_matching_does_not_guess_between_two_swapped_shifts():
    previous = [
        S("2026-10-19", "12:00", "17:00", "Location A"),
        S("2026-10-20", "09:00", "14:00", "Location B"),
    ]
    current = [
        S("2026-10-19", "09:00", "14:00", "Location B"),
        S("2026-10-20", "12:00", "17:00", "Location A"),
    ]
    events = diff(V(1, previous), V(2, current))
    lines = evaluate(events, {e.id: NO_ANS for e in events}, YES, 2000)

    assert total(lines) == 0
    assert all(line.status == "needs_review" for line in lines)


# from review test_core_fix_5
def test_move_out_of_two_shift_day_does_not_pay_as_new_shift():
    previous = [
        S("2026-10-19", "09:00", "12:00", "Location A"),
        S("2026-10-19", "14:00", "18:00", "Location A"),
    ]
    current = [
        S("2026-10-19", "09:00", "12:00", "Location A"),
        S("2026-10-20", "14:00", "18:00", "Location B"),
    ]

    events = diff(V(1, previous), V(2, current))
    lines = evaluate(events, {e.id: NO_ANS for e in events}, YES, 2000)

    assert total(lines) == 0
    assert all(line.status == "needs_review" for line in lines)


# from review test_core_fix_6
def test_swapped_dates_with_changed_hours_are_not_paid_as_same_day_changes():
    previous = [
        S("2026-10-19", "09:00", "18:00", "Location A"),
        S("2026-10-20", "12:00", "17:00", "Location B"),
    ]
    current = [
        S("2026-10-19", "12:00", "18:00", "Location B"),
        S("2026-10-20", "09:00", "19:00", "Location A"),
    ]

    events = diff(V(1, previous), V(2, current))
    lines = evaluate(events, {e.id: NO_ANS for e in events}, YES, 2000)

    assert total(lines) == 0
    assert all(line.status == "needs_review" for line in lines)


# from review test_m1_1
def test_malformed_resource_uri_uses_valid_metadata_url():
    item = ResourceContent(
        resource_id=uuid4(),
        resource=Resource(uri="http://[bad", metadata={"url": "https://cdn.test/schedule.png"}),
    )
    assert image_url(item) == "https://cdn.test/schedule.png"


def test_malformed_download_url_raises_download_error():
    with pytest.raises(DownloadError):
        download("http://[bad")


# from review test_m1_2
def test_download_rejects_empty_image_body():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, headers={"content-type": "image/png"}, content=b"")
    )
    with pytest.raises(DownloadError):
        download("https://cdn.test/empty.png", transport)


def test_download_caps_redirect_body():
    def respond(request):
        if request.url.path == "/redirect":
            return httpx.Response(
                302,
                headers={"location": "/schedule.png"},
                stream=httpx.ByteStream(b"x" * (MAX_BYTES + 1)),
            )
        return httpx.Response(200, headers={"content-type": "image/png"}, content=b"png")

    with pytest.raises(DownloadError, match="too large"):
        download("https://cdn.test/redirect", httpx.MockTransport(respond))


# from review test_m2_1
def test_empty_extraction_is_unreadable(monkeypatch):
    monkeypatch.setattr(extract, "_gemini", lambda *_: '{"shifts": []}')

    assert extract.extract(b"not a schedule", "image/png", "Maria Lopez", date(2026, 10, 18)) == (
        [], ["unreadable"]
    )


# from review test_m2_2
def test_missing_ambiguous_flag_rejects_row(monkeypatch):
    monkeypatch.setattr(
        extract,
        "_gemini",
        lambda *_: '{"shifts": [{"month": 10, "day": 20, "start": "09:00", "end": "17:00", "location": null}]}',
    )

    assert extract.extract(b"schedule", "image/png", "Maria Lopez", date(2026, 10, 18)) == (
        [], ["unreadable"]
    )


# from review test_m2_3
def test_interactions_fallback_declares_json_response_mime(monkeypatch):
    def generate_content(**_):
        raise TypeError("generate_content signature unavailable")

    def create(**kwargs):
        assert kwargs["response_mime_type"] == "application/json"
        return SimpleNamespace(output_text='{"shifts": []}')

    client = SimpleNamespace(
        models=SimpleNamespace(generate_content=generate_content),
        interactions=SimpleNamespace(create=create),
    )
    monkeypatch.setattr(extract.genai, "Client", lambda **_: client)

    assert extract._gemini(b"image", "image/png", "prompt") == '{"shifts": []}'


# from review test_m2_4
def test_duplicate_identical_rows_are_collapsed(monkeypatch):
    monkeypatch.setattr(
        extract,
        "_gemini",
        lambda *_: (
            '{"shifts": ['
            '{"month": 10, "day": 20, "start": "09:00", "end": "17:00", "location": "Westwood", "ambiguous": false},'
            '{"month": 10, "day": 20, "start": "09:00", "end": "17:00", "location": "Westwood", "ambiguous": false}'
            ']}'
        ),
    )

    shifts, warnings = extract.extract(b"schedule", "image/png", "Maria Lopez", date(2026, 10, 18))

    assert len(shifts) == 1
    assert warnings == []


# from review test_m2_5
def test_interactions_fallback_5xx_has_one_retry(monkeypatch):
    requests = []

    def unavailable(request):
        requests.append(request)
        return httpx.Response(503, json={"error": {"code": 503, "message": "retry", "status": "UNAVAILABLE"}})

    with httpx.Client(transport=httpx.MockTransport(unavailable)) as http:
        real_client = genai.Client(api_key="fake", http_options=types.HttpOptions(httpx_client=http, timeout=20_000))

        def unavailable_primary(**_):
            raise TypeError("generate_content is unavailable")

        client = SimpleNamespace(
            models=SimpleNamespace(generate_content=unavailable_primary),
            interactions=real_client.interactions,
        )
        monkeypatch.setattr(extract.genai, "Client", lambda **_: client)

        assert extract.extract(b"image", "image/png", "Maria Lopez", date(2026, 10, 18)) == (
            [], ["unreadable"]
        )

    assert len(requests) == 2


# from review test_m3_1
def test_start_session_lists_missing_onboarding_fields(tmp_path, monkeypatch):
    path = str(tmp_path / "start.db")
    db.init(path)
    monkeypatch.setattr(agent, "DB_PATH", path)

    class Ctx:
        def __init__(self):
            self.out = []

        async def send(self, recipient, message):
            self.out.append(message)

        class logger:
            @staticmethod
            def info(*args):
                pass

            @staticmethod
            def error(*args):
                pass

    ctx = Ctx()
    msg = ChatMessage(msg_id=uuid4(), content=[StartSessionContent()])
    asyncio.run(agent.on_chat(ctx, "worker", msg))
    replies = [c.text for m in ctx.out if isinstance(m, ChatMessage)
               for c in m.content if isinstance(c, TextContent)]
    assert len(replies) == 1
    assert [replies[0].index(field) for field in
            ("NAME", "RATE", "EMPLOYER", "TITLE", "STORE", "MANAGER", "COVER")] == sorted(
                replies[0].index(field) for field in
                ("NAME", "RATE", "EMPLOYER", "TITLE", "STORE", "MANAGER", "COVER"))


# from review test_m3_2
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


# from review test_m3_3
def test_multiline_input_cannot_bypass_parser_size_limit(tmp_path, monkeypatch):
    path = str(tmp_path / "long.db")
    db.init(path)
    monkeypatch.setattr(agent, "DB_PATH", path)
    text = ("NAME " + "x" * 100 + "\n") * 25 + "RATE 99"
    assert len(text) > 2000
    agent.handle_text("worker", text)
    data, _ = db.get_profile(path, "worker")
    assert "rate" not in data


# from review test_m3_4
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


# from review test_m3_5
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


# from review test_m3_6
def test_duplicate_image_during_onboarding_is_acknowledged_as_duplicate(tmp_path, monkeypatch):
    path = str(tmp_path / "duplicate.db")
    db.init(path)
    monkeypatch.setattr(agent, "DB_PATH", path)
    agent.PENDING_IMAGES.clear()

    first = agent.handle_image("worker", b"same image", "image/png")
    second = agent.handle_image("worker", b"same image", "image/png")

    assert "once you are set up" in first[0]
    assert second == ["Already have this one."]


# from review test_m3_7
def test_empty_confirmed_version_cancels_earlier_week(tmp_path, monkeypatch):
    path = str(tmp_path / "cancel.db")
    db.init(path)
    monkeypatch.setattr(agent, "DB_PATH", path)
    monkeypatch.setattr(agent, "_today", lambda: date(2026, 10, 18))
    agent.handle_text("worker", "\n".join([
        "NAME Maria Lopez", "RATE 20", "EMPLOYER Big Retail Co", "TITLE Cashier",
        "STORE Westwood, Los Angeles", "MANAGER boss@example.com", "COVER yes yes yes",
    ]))
    agent.handle_text("worker", schedule_text([S("2026-10-20", "09:00", "17:00")]))
    agent.handle_text("worker", "GOT 2026-10-03")
    agent.handle_text("worker", "CONFIRM")
    agent.handle_text("worker", schedule_text([S("2026-10-20", "10:00", "18:00")]))
    agent.handle_text("worker", "GOT 2026-10-17")
    agent.handle_text("worker", "DROP 2026-10-20")
    response = "\n".join(agent.handle_text("worker", "CONFIRM"))

    assert "shift cancelled" in response
    assert "Q1 " in response and "Q2 " in response


# from review test_m3_8
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


# from review test_m3_9
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


# from review test_sweep_1
def test_negated_send_prose_does_not_authorize_email():
    assert parse("Do not send receipt 7 to my manager.") is None


# from review test_sweep_10
def test_rest_premium_due_after_shift_ends_on_its_day(A, monkeypatch):
    for text in ("\n".join(SETUP), schedule_text([
        S("2026-10-23", "16:00", "23:00"),
        S("2026-10-24", "07:00", "15:00"),
    ]), "GOT 2026-10-03", "CONFIRM"):
        say(A, "worker", text)

    class AfterShift(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 24, 20, 0, tzinfo=tz)

    monkeypatch.setattr(agent, "datetime", AfterShift)
    response = say(A, "worker", "RECEIPT")
    profile, _ = db.get_profile(A.DB_PATH, "worker")
    assert "Notice preview" in response
    assert any(line["rule"] == "R6" for line in profile["notice"]["lines"])


# from review test_sweep_11
def test_amount_on_card_has_legal_note(monkeypatch):
    monkeypatch.setattr(agent, "CARDS", True)
    card = agent._card(7, 7000, "boss@example.com")
    assert card is not None
    payload = json.loads(card.metadata["card_payload"])
    assert "Not legal advice" in json.dumps(payload)


# from review test_sweep_2
def test_daylight_saving_cancelled_shift_uses_elapsed_hours():
    for day, learned, expected_cents in (
        ("2026-11-01", "2026-10-30T09:00", 5000),  # clocks fall back: five elapsed hours
        ("2026-03-08", "2026-03-01T09:00", 3000),  # clocks spring forward: three elapsed hours
    ):
        events = diff(V(1, [S(day, "00:00", "04:00")]), V(2, [], learned))
        lines = evaluate(events, {e.id: NO_ANS for e in events}, YES, 2000)
        assert lines[0].cents == expected_cents


# from review test_sweep_3
def test_notice_limit_counts_send_day_not_creation_day(tmp_path):
    path = str(tmp_path / "cap.db")
    db.init(path)
    yesterday = (datetime.now(LA) - timedelta(days=1)).isoformat()
    old = db.create_notice(path, "worker", [], 100)
    with db.conn(path) as c:
        c.execute("UPDATE notices SET created_at=? WHERE id=?", (yesterday, old))
    assert db.claim_notice(path, "worker", old)
    db.finish_notice(path, "worker", old, "<old>")
    second = db.create_notice(path, "worker", [], 100)
    assert db.claim_notice(path, "worker", second)
    db.finish_notice(path, "worker", second, "<second>")
    third = db.create_notice(path, "worker", [], 100)
    assert db.claim_notice(path, "worker", third) is False


# from review test_sweep_4
def test_changing_manager_invalidates_old_notice_preview(A, monkeypatch):
    preview = golden(A, "worker")[-1]
    nid = re.search(r"reply SEND (\d+)", preview)[1]
    sent_to = []
    monkeypatch.setattr(notice, "send", lambda to, pdf, name: sent_to.append(to) or "<message>")
    say(A, "worker", "MANAGER new@example.com")
    response = say(A, "worker", f"SEND {nid}")
    assert sent_to == [] and "not pending" in response


# from review test_sweep_5
def test_next_week_schedule_is_not_change_to_previous_week(A):
    say(A, "worker", "\n".join(SETUP))
    say(A, "worker", schedule_text([S("2026-10-20", "09:00", "17:00")]))
    say(A, "worker", "GOT 2026-10-03")
    say(A, "worker", "CONFIRM")
    say(A, "worker", schedule_text([S("2026-10-27", "09:00", "17:00")]))
    say(A, "worker", "GOT 2026-10-17")
    response = say(A, "worker", "CONFIRM")
    assert "Q1" not in response
    assert "Estimated total: $0.00" in response


# from review test_sweep_6
def test_corrected_schedule_can_later_reappear_as_new_version(A):
    say(A, "worker", "\n".join(SETUP))
    original = schedule_text([S("2026-10-20", "09:00", "17:00")])
    say(A, "worker", original)
    say(A, "worker", "EDIT 2026-10-20 10:00-18:00")
    say(A, "worker", "CONFIRM")
    response = say(A, "worker", original)
    assert "Here is what I read" in response


# from review test_sweep_7
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


# from review test_sweep_9
def test_concurrent_schedule_then_got_keeps_the_stated_date(A, monkeypatch):
    say(A, "worker", "\n".join(SETUP))
    first_id, second_id = uuid4(), uuid4()
    entered, release = Event(), Event()
    real_first_time = db.first_time

    def slow_first_time(path, key):
        if key.endswith(str(first_id)):
            entered.set()
            assert release.wait(2)
        return real_first_time(path, key)

    monkeypatch.setattr(db, "first_time", slow_first_time)

    async def deliver():
        schedule = ChatMessage(msg_id=first_id, content=[TextContent(text=schedule_text(
            [S("2026-10-20", "09:00", "17:00")]))])
        got = ChatMessage(msg_id=second_id, content=[TextContent(text="GOT 2026-10-03")])
        first = asyncio.create_task(A.on_chat(Ctx(), "worker", schedule))
        assert await asyncio.to_thread(entered.wait, 2)
        second = asyncio.create_task(A.on_chat(Ctx(), "worker", got))
        await asyncio.sleep(0.1)
        release.set()
        await asyncio.gather(first, second)

    asyncio.run(deliver())
    versions = db.versions(A.DB_PATH, "worker", confirmed_only=False)
    assert len(versions) == 1
    assert versions[0].learned_at.date() == date(2026, 10, 3)
