"""Same-sender commands must be applied in arrival order when handlers run together."""
import asyncio
from datetime import date
from threading import Event
from uuid import uuid4

from conftest import S
from extract import schedule_text
from test_flow import A, Ctx, SETUP, say  # noqa: F401
from uagents_core.contrib.protocols.chat import ChatMessage, TextContent

import db


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
