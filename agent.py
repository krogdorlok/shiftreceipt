"""ShiftReceipt agent: ASI:One Chat Protocol front end. M1 skeleton: ack, dedupe, image download, parse."""
import asyncio
import os
import time
from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (ChatAcknowledgement, ChatMessage, MetadataContent,
                                                 ResourceContent, StartSessionContent, TextContent,
                                                 chat_protocol_spec)

import db
from parser import parse

load_dotenv()
DB_PATH = os.getenv("DB_PATH", "shiftreceipt.db")
MAX_BYTES = 10 * 1024 * 1024
TIMEOUT_S = 10

SCHEDULE_EXAMPLE = "```\nSCHEDULE\n2026-10-20 09:00-17:00 Westwood\n2026-10-22 12:00-20:00 Westwood\n```"
HELP_TEXT = ("ShiftReceipt checks your work schedule against the LA Fair Work Week Ordinance. Send a screenshot "
             "of each schedule you get. I compare the versions, show which last minute changes may be owed "
             "predictability pay, and prepare a draft notice to your employer that is only sent if you type SEND. "
             "You can also type your schedule like this:\n\n" + SCHEDULE_EXAMPLE + "\n\nNot legal advice.")
FALLBACK_TEXT = "I could not open that image. You can type your schedule instead:\n\n" + SCHEDULE_EXAMPLE


class DownloadError(Exception):
    """Message is safe to log: never contains the URL."""


def download(url: str, transport: httpx.BaseTransport | None = None) -> tuple[bytes, str]:
    if not _http(url):
        raise DownloadError("bad or non-http url")
    deadline = time.monotonic() + TIMEOUT_S
    try:
        with httpx.Client(timeout=TIMEOUT_S, follow_redirects=True, transport=transport) as client:
            with client.stream("GET", url) as r:
                if r.status_code != 200:
                    raise DownloadError(f"http {r.status_code}")
                mime = r.headers.get("content-type", "").split(";")[0].strip().lower()
                if not mime.startswith("image/"):
                    raise DownloadError("not an image")
                if int(r.headers.get("content-length") or 0) > MAX_BYTES:
                    raise DownloadError("too large")
                buf = bytearray()
                for chunk in r.iter_bytes():
                    buf += chunk
                    if len(buf) > MAX_BYTES:
                        raise DownloadError("too large")
                    if time.monotonic() > deadline:  # read timeout is per chunk; cap the total too
                        raise DownloadError("timeout")
                return bytes(buf), mime
    except httpx.TimeoutException:
        raise DownloadError("timeout") from None
    except (httpx.HTTPError, ValueError) as e:  # str(e) can contain the URL, so log only the type
        raise DownloadError(type(e).__name__) from None


def _http(u) -> bool:
    try:
        return isinstance(u, str) and urlparse(u).scheme in ("http", "https") and bool(urlparse(u).hostname)
    except ValueError:  # e.g. "http://[bad"
        return False


def image_url(item: ResourceContent) -> str | None:
    """First http(s) URL from resource.uri or metadata url/uri/source/image_url, across all resources."""
    resources = item.resource if isinstance(item.resource, list) else [item.resource]
    for res in resources:
        for u in [res.uri] + [(res.metadata or {}).get(k) for k in ("url", "uri", "source", "image_url")]:
            if _http(u):
                return u
    return None


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def reply(ctx: Context, to: str, text: str) -> None:
    await ctx.send(to, ChatMessage(timestamp=_now(), msg_id=uuid4(), content=[TextContent(type="text", text=text)]))


chat = Protocol(spec=chat_protocol_spec)


@chat.on_message(ChatMessage)
async def on_chat(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(sender, ChatAcknowledgement(timestamp=_now(), acknowledged_msg_id=msg.msg_id))
    if not await asyncio.to_thread(db.first_time, DB_PATH, f"{sender}:{msg.msg_id}"):
        return
    ctx.logger.info(f"msg {msg.msg_id} from {sender[:16]} items={len(msg.content)}")
    for item in msg.content:
        try:
            await handle_item(ctx, sender, item)
        except Exception as e:  # never crash the handler on one bad item
            ctx.logger.error(f"msg {msg.msg_id} failed: {type(e).__name__}")
            await reply(ctx, sender, "Something went wrong on my side. Please try again.")


async def handle_item(ctx: Context, sender: str, item) -> None:
    if isinstance(item, StartSessionContent):
        await ctx.send(sender, ChatMessage(timestamp=_now(), msg_id=uuid4(),
                                           content=[MetadataContent(type="metadata",
                                                                    metadata={"attachments": "true"})]))
    elif isinstance(item, ResourceContent):
        url = image_url(item)
        try:
            if not url:
                raise DownloadError("no url")
            data, _mime = await asyncio.to_thread(download, url)
        except DownloadError as e:
            ctx.logger.info(f"image download failed: {e}")
            await reply(ctx, sender, FALLBACK_TEXT)
            return
        await reply(ctx, sender, f"Got your schedule image ({max(1, round(len(data) / 1024))} KB)")
    elif isinstance(item, TextContent):
        c = parse(item.text)
        await reply(ctx, sender, f"Understood: {c.name}" if c and c.name != "HELP" else HELP_TEXT)


@chat.on_message(ChatAcknowledgement)
async def on_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info(f"ack {msg.acknowledged_msg_id} from {sender[:16]}")


def main() -> None:
    seed = os.getenv("AGENT_SEED")
    if not seed:
        raise SystemExit("AGENT_SEED missing from .env")
    db.init(DB_PATH)
    agent = Agent(name=os.getenv("AGENT_NAME", "shiftreceipt"), seed=seed, port=int(os.getenv("AGENT_PORT", "8001")),
                  mailbox=True, readme_path="README_AGENT.md",
                  description="Checks LA Fair Work Week schedule changes and drafts a predictability pay notice.",
                  publish_agent_details=True, handle_messages_concurrently=True)
    agent.include(chat, publish_manifest=True)

    @agent.on_event("startup")
    async def hello(ctx: Context):
        ctx.logger.info(f"Agent address: {agent.address}")
        ctx.logger.info("open the Agent Inspector link above, connect Mailbox")

    agent.run()


if __name__ == "__main__":
    main()
