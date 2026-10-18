"""The chat session should start the M3 onboarding flow."""
import asyncio
from uuid import uuid4

from uagents_core.contrib.protocols.chat import ChatMessage, StartSessionContent, TextContent

import agent
import db


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
