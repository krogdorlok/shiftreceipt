import asyncio
import json
from uuid import uuid4

from uagents_core.contrib.protocols.chat import ChatMessage, MetadataContent, TextContent

from conftest import fixture
from extract import schedule_text
from parser import parse
from test_flow import A, Ctx, golden, say  # noqa: F401


def test_manager_mode_estimates_cost_and_never_offers_send(A):
    assert "Manager mode" in say(A, "m", "MODE manager")
    assert "current schedule" in say(A, "m", schedule_text(fixture("v1")))
    assert "RATE" in say(A, "m", schedule_text(fixture("v2")))
    say(A, "m", "RATE 20")
    r = say(A, "m", schedule_text(fixture("v2")))
    assert "would cost about $70.00 in predictability pay (Rule 5)" in r and "14+ days ahead cost $0" in r
    assert "SEND" not in r and "RECEIPT" not in say(A, "m", "RECEIPT")
    assert "Worker mode" in say(A, "m", "MODE worker")
    assert "To set up" in say(A, "m", "hello")


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
