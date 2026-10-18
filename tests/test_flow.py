import asyncio
import importlib
import json
import logging
import re
from uuid import uuid4

import pytest
from uagents_core.contrib.protocols.chat import ChatMessage, MetadataContent, TextContent

import agent as agent_mod
import db
from conftest import fixture
from extract import schedule_text
from parser import parse


class Ctx:
    logger = logging.getLogger("test")

    def __init__(self):
        self.out = []

    async def send(self, to, msg):
        self.out.append((to, msg))


@pytest.fixture
def A(tmp_path, monkeypatch):
    path = str(tmp_path / "t.db")
    db.init(path)
    monkeypatch.setattr(agent_mod, "DB_PATH", path)
    agent_mod.PENDING_IMAGES.clear()
    agent_mod.LOCKS.clear()
    return agent_mod


def say(A, sender, text, msg_id=None):
    ctx = Ctx()
    asyncio.run(A.on_chat(ctx, sender, ChatMessage(content=[TextContent(text=text)], msg_id=msg_id or uuid4())))
    return "\n".join(c.text for to, m in ctx.out if to == sender and isinstance(m, ChatMessage)
                     for c in m.content if isinstance(c, TextContent))


SETUP = ["NAME Maria Lopez", "RATE 20", "EMPLOYER Big Retail Co", "TITLE Cashier", "STORE Westwood, Los Angeles",
         "MANAGER boss@example.com", "COVER yes yes yes"]


def golden(A, sender, upto=None):
    replies = []
    steps = SETUP + [schedule_text(fixture("v1")), "GOT 2026-10-03", "CONFIRM",
                     schedule_text(fixture("v2")), "GOT 2026-10-17", "CONFIRM"]
    for s in steps[:upto]:
        replies.append(say(A, sender, s))
    if upto is None:
        for q in re.findall(r"^Q(\d+) ", replies[-1], re.M):
            replies.append(say(A, sender, f"Q{q} no"))
    return replies


def test_golden_script(A):
    r = golden(A, "maria")
    assert r[0].startswith("**Hi, I am ShiftReceipt.**") and "How it works" in r[0]  # greeting on first message
    assert "To set up" in r[0] and "NAME" not in r[0].split("To set up")[1] and "RATE" in r[0]
    assert "COVER: three yes/no answers" in r[5] and "(3) Do you work 2 or more hours" in r[5] and "(4)" not in r[5]
    assert "Tue Oct 20 9:00 AM-5:00 PM Westwood" in r[7] and "CONFIRM" in r[7]
    assert "baseline" in r[9]
    qs = re.findall(r"^Q\d+ ", r[12], re.M)
    assert len(qs) == 5 and "Did you ask for this change?" in r[12]
    final = r[-1]
    assert "**Tue Oct 20, shift moved**: from 9:00 AM-5:00 PM to 1:00 PM-9:00 PM. **$20.00 may be owed**" in final
    assert "**Thu Oct 22, hours cut**: from 12:00 PM-6:00 PM to 12:00 PM-3:00 PM. **$30.00 may be owed**" in final
    assert "**Sun Oct 25, hours added**: from 10:00 AM-4:00 PM to 10:00 AM-6:00 PM. **$20.00 may be owed**" in final
    assert "**Sat Oct 24, under 10 hours rest**" in final and "**$80.00 may be owed if you work it**" in final
    assert "**Notice preview:** Big Retail Co may owe Maria Lopez **$70.00**" in final
    assert "Schedule change pay that may be owed: $70.00" in final
    assert "Estimated total: $150.00" in final
    assert "reply SEND 1 to email the official Notice to Cure to boss@example.com" in final
    assert "Not legal advice" in final and "—" not in final and "you are owed" not in final.lower()


def test_duplicate_message_ignored(A):
    mid = uuid4()
    assert "Saved" in say(A, "u", "NAME Maria", mid)
    assert say(A, "u", "NAME Someone Else", mid) == ""
    assert db.get_profile(A.DB_PATH, "u")[0]["name"] == "Maria"


def test_two_senders_stay_separate(A):
    for a, b in zip(SETUP, SETUP):
        say(A, "alice", a)
        say(A, "bob", b.replace("Maria Lopez", "Bob Ng").replace("RATE 20", "RATE 30"))
    say(A, "alice", schedule_text(fixture("v1")))
    assert "No confirmed schedule" in say(A, "bob", "RECEIPT")
    assert "Nothing waiting" in say(A, "bob", "CONFIRM")
    assert "Confirmed" in say(A, "alice", "CONFIRM")
    assert db.get_profile(A.DB_PATH, "bob")[0]["name"] == "Bob Ng"
    assert len(db.versions(A.DB_PATH, "alice")) == 1 and db.versions(A.DB_PATH, "bob") == []


def test_restart_mid_flow_continues(A, monkeypatch):
    golden(A, "maria", upto=11)  # v2 sent and GOT, not confirmed
    path = A.DB_PATH
    B = importlib.reload(agent_mod)  # new process: module state gone, same DB file
    monkeypatch.setattr(B, "DB_PATH", path)
    r = say(B, "maria", "CONFIRM")
    assert "Q5 " in r
    for q in range(1, 6):
        last = say(B, "maria", f"Q{q} no")
    assert "Estimated total: $150.00" in last


def test_schedule_before_setup_is_kept(A):
    assert "once you are set up" in say(A, "u", schedule_text(fixture("v1")))
    for s in SETUP[:-1]:
        say(A, "u", s)
    r = say(A, "u", "COVER yes yes yes")
    assert "You are set up" in r and "Tue Oct 20 9:00 AM-5:00 PM" in r


def test_pasted_setup_lines_and_duplicate_schedule(A):
    assert "You are set up" in say(A, "u", "\n".join(SETUP))
    v1 = schedule_text(fixture("v1"))
    say(A, "u", v1)
    assert "Here is what I read" in say(A, "u", v1)  # unconfirmed: shown again for review
    say(A, "u", "CONFIRM")
    assert say(A, "u", v1) == "Already have this one."


def test_edit_drop_got_and_unknown(A):
    say(A, "u", "\n".join(SETUP))
    say(A, "u", schedule_text(fixture("v1")))
    assert "Tue Oct 20 10:00 AM-6:00 PM" in say(A, "u", "EDIT 2026-10-20 10:00-18:00")
    assert "Thu Oct 22" not in say(A, "u", "DROP 2026-10-22")
    assert "No shift" in say(A, "u", "DROP 2026-10-22")
    assert "future" in say(A, "u", "GOT 2099-01-01")
    assert "got on Sat Oct 3" in say(A, "u", "GOT 2026-10-03")
    assert "could not read" in say(A, "u", "what is this?") and "Then CONFIRM" in say(A, "u", "what is this?2")
    assert "No open questions" in say(A, "u", "Q9 yes")


def test_reset_only_for_demo_senders(A, monkeypatch):
    say(A, "u", "NAME Maria")
    assert "only available" in say(A, "u", "RESET")
    monkeypatch.setattr(A, "DEMO_SENDERS", {"u"})
    assert "Reset done" in say(A, "u", "RESET")
    assert db.get_profile(A.DB_PATH, "u")[0] == {}


def test_not_covered_skips_questions_and_amounts(A):
    say(A, "u", "\n".join(SETUP[:-1] + ["COVER yes yes no"]))
    for s in (schedule_text(fixture("v1")), "GOT 2026-10-03", "CONFIRM", schedule_text(fixture("v2")), "CONFIRM"):
        r = say(A, "u", s)
    assert "Q1" not in r and "Estimated total: $0.00" in r and "SEND" not in r


def test_next_week_is_not_a_change_and_edited_reupload_is_new(A):
    from conftest import S
    say(A, "u", "\n".join(SETUP))
    for s in (schedule_text([S("2026-10-20", "09:00", "17:00")]), "GOT 2026-10-03", "CONFIRM",
              schedule_text([S("2026-10-27", "09:00", "17:00")]), "GOT 2026-10-17"):
        say(A, "u", s)
    r = say(A, "u", "CONFIRM")
    assert "Q1" not in r and "Estimated total: $0.00" in r
    original = schedule_text([S("2026-11-03", "09:00", "17:00")])
    for s in (original, "EDIT 2026-11-03 10:00-18:00", "CONFIRM"):
        say(A, "u", s)
    assert "Here is what I read" in say(A, "u", original)


def test_prose_send_is_not_a_send(A):
    assert "type SEND 7" in say(A, "u", "Please send receipt 7")
    assert "To set up" in say(A, "u", "Do not send receipt 7")  # negated: not a command at all


def test_stale_preview_needs_fresh_receipt(A):
    nid = re.search(r"reply SEND (\d+)", golden(A, "maria")[-1])[1]
    data, _ = db.get_profile(A.DB_PATH, "maria")
    db.update_profile(A.DB_PATH, "maria", notice={**data["notice"], "day": "2026-01-01"})
    assert "earlier day" in say(A, "maria", f"SEND {nid}")


def test_receipt_card_follows_text_and_click_parses(A):
    golden(A, "maria", upto=13)  # through v2 CONFIRM (questions)
    ctx = Ctx()
    for q in range(1, 6):
        ctx = Ctx()
        asyncio.run(A.on_chat(ctx, "maria", ChatMessage(content=[TextContent(text=f"Q{q} no")], msg_id=uuid4())))
    msgs = [m for _, m in ctx.out if isinstance(m, ChatMessage)]
    assert isinstance(msgs[-2].content[0], TextContent) and isinstance(msgs[-1].content[0], MetadataContent)
    meta = msgs[-1].content[0].metadata
    assert all(isinstance(v, str) for v in meta.values()) and len(json.dumps(meta)) < 64_000
    sel = json.loads(meta["card_payload"])["cta"]["selection"]
    assert parse(sel).name == "SEND" and str(parse(sel).args["id"]) in msgs[-2].content[0].text


def test_cards_kill_switch(A, monkeypatch):
    monkeypatch.setattr(A, "CARDS", False)
    golden(A, "maria", upto=13)
    for q in range(1, 6):
        ctx = Ctx()
        asyncio.run(A.on_chat(ctx, "maria", ChatMessage(content=[TextContent(text=f"Q{q} no")], msg_id=uuid4())))
    assert all(isinstance(m.content[0], TextContent) for _, m in ctx.out if isinstance(m, ChatMessage))


AT = "@agent1qffxdzuxgw6ad4k6dmlsfxd4h7ey26mgsfs0nt6lkgz8wv97z4w7wfexzpq "


def test_asi_one_mention_and_one_line_setup(A):
    r = say(A, "u", AT + "NAME Maria Lopez RATE 20 EMPLOYER Case TITLE Secretary STORE La Cienega, Los Angeles "
                         "MANAGER boss@example.com COVER yes yes yes")
    assert "You are set up" in r
    data, _ = db.get_profile(A.DB_PATH, "u")
    assert (data["name"], data["rate"], data["employer"], data["store"]) == ("Maria Lopez", 2000, "Case",
                                                                           "La Cienega, Los Angeles")
    r = say(A, "u", AT + "SCHEDULE 2026-10-20 09:00-17:00 Westwood 2026-10-22 12:00-18:00 Westwood")
    assert "1. Tue Oct 20 9:00 AM-5:00 PM Westwood" in r and "2. Thu Oct 22" in r
    assert "baseline" in say(A, "u", AT + "GOT 2026-10-03 CONFIRM")


def test_missing_keywords_get_a_copyable_block(A):
    # what was actually sent from ASI:One: keywords missing for employer, manager and cover
    r = say(A, "u", AT + "NAME Maria Lopez RATE 20 Case TITLE Secretary STORE La Cienega, Los Angeles "
                         "lalisinghal36@example.com yes yes yes")
    assert "I could not read: RATE 20 Case" in r
    assert "```\nEMPLOYER Big Retail Co\nRATE 20\n" not in r and "EMPLOYER Big Retail Co" in r and "COVER yes yes yes" in r
    assert say(A, "u", "@shiftreceipt hi").startswith("I could not read that.")


def test_unreadable_text_gets_a_hint_for_where_you_are(A):
    nid = re.search(r"reply SEND (\d+)", golden(A, "maria")[-1])[1]
    assert "To email your notice, type SEND 1." in say(A, "maria", AT + nid)
    assert f"Did you mean: SEND {nid}" in say(A, "maria", f"SNED {nid}")
    say(A, "maria", schedule_text(fixture("v3")))
    assert "Then CONFIRM" in say(A, "maria", "ok")


def test_send_number_is_always_1(A, monkeypatch):
    import notice
    sent = []
    monkeypatch.setattr(notice, "send", lambda to, pdf, name: sent.append(to) or "<m>")
    monkeypatch.setattr(A, "DEMO_SENDERS", {"maria", "bob"})
    for run in range(3):  # three demo runs, two users: always SEND 1
        for who in ("maria", "bob"):
            assert "reply SEND 1 to email" in golden(A, who)[-1]
        assert say(A, "maria", "SEND 1").startswith("Sent")
        assert "not pending" in say(A, "maria", "SEND 1") and "not pending" in say(A, "maria", "SEND 2")
        assert "Reset done" in say(A, "maria", "RESET") and "Reset done" in say(A, "bob", "RESET")
    assert len(sent) == 3


def test_first_message_gets_greeting_and_steps(A):
    r = say(A, "new", "hi")
    assert r.startswith("**Hi, I am ShiftReceipt.**") and "1. Set up once" in r and "5. I show a receipt" in r
    assert "To set up" in r and "could not read" not in r
    assert "Hi, I am ShiftReceipt" not in say(A, "new", "NAME Ana")  # only once
