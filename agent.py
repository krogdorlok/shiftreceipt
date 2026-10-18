"""ShiftReceipt agent: ASI:One Chat Protocol front end and the worker flow (state per sender in SQLite)."""
import asyncio
import difflib
import hashlib
import json
import logging
import os
import re
import time as clock
from collections import defaultdict
from datetime import date, datetime, time, timezone
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (ChatAcknowledgement, ChatMessage, MetadataContent,
                                                 ResourceContent, StartSessionContent, TextContent,
                                                 chat_protocol_spec)

import db
import notice
import rules
from diff import diff
from extract import extract, schedule_text
from models import LA, Answers, Coverage, Shift
from parser import _from_json, _strict, parse

load_dotenv()
DB_PATH = os.getenv("DB_PATH", "shiftreceipt.db")
MAX_BYTES = 10 * 1024 * 1024
TIMEOUT_S = 10
MAX_REDIRECTS = 5

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
    deadline = clock.monotonic() + TIMEOUT_S
    try:
        with httpx.Client(timeout=TIMEOUT_S, transport=transport) as client:
            for _ in range(MAX_REDIRECTS + 1):  # follow redirects by hand so no redirect body is ever read
                with client.stream("GET", url) as r:
                    if not (r.is_redirect and r.next_request):
                        return _read(r, deadline)
                    _drain(r, deadline)
                    url = str(r.next_request.url)
                if not _http(url):
                    raise DownloadError("bad redirect")
            raise DownloadError("too many redirects")
    except httpx.TimeoutException:
        raise DownloadError("timeout") from None
    except (httpx.HTTPError, ValueError) as e:  # str(e) can contain the URL, so log only the type
        raise DownloadError(type(e).__name__) from None


def _drain(r: httpx.Response, deadline: float) -> None:
    """Redirect bodies are discarded, but still capped in size and time."""
    n = 0
    for chunk in r.iter_bytes():
        n += len(chunk)
        if n > MAX_BYTES:
            raise DownloadError("too large")
        if clock.monotonic() > deadline:
            raise DownloadError("timeout")


def _read(r: httpx.Response, deadline: float) -> tuple[bytes, str]:
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
        if clock.monotonic() > deadline:  # read timeout is per chunk; cap the total too
            raise DownloadError("timeout")
    if not buf:
        raise DownloadError("empty")
    return bytes(buf), mime


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


async def reply(ctx: Context, to: str, item: "str | MetadataContent") -> None:
    if isinstance(item, MetadataContent):  # a card: always sent after its text, and never breaks the flow
        try:
            await ctx.send(to, ChatMessage(timestamp=_now(), msg_id=uuid4(), content=[item]))
        except Exception as e:
            ctx.logger.error(f"card failed: {type(e).__name__}")
        return
    await ctx.send(to, ChatMessage(timestamp=_now(), msg_id=uuid4(), content=[TextContent(type="text", text=item)]))


# ---- M3 worker flow. Sync on purpose: the handler runs it in asyncio.to_thread (db, Gemini). ----
DEMO_SENDERS = {s.strip() for s in os.getenv("DEMO_SENDERS", "").split(",") if s.strip()}
# Images that arrive before NAME (needed to pick the worker's row) wait here, in memory only: images are never
# stored. Once NAME is known they are read at once and saved as versions, so later steps survive a restart.
PENDING_IMAGES: dict[str, list[tuple[bytes, str, str]]] = defaultdict(list)
LOCKS: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)  # one message at a time per sender

COVER_TEXT = ("Three yes/no questions: (1) Is your employer a retail business? (2) Does it have 300+ employees "
              "worldwide? (3) Is your store inside the City of Los Angeles (not Santa Monica, Culver City, Burbank, "
              "Glendale, Beverly Hills, Pasadena) and do you work 2+ hours a week there? Reply e.g. COVER yes yes yes")
STEPS = [("name", "NAME your full name, e.g. NAME Maria Lopez"),
         ("rate", "RATE your hourly pay, e.g. RATE 20"),
         ("employer", "EMPLOYER the company you work for"),
         ("title", "TITLE your job title, e.g. TITLE Cashier"),
         ("store", "STORE your store and city, e.g. STORE Westwood, Los Angeles"),
         ("manager", "MANAGER the email of the person who sets your schedule"),
         ("cover", COVER_TEXT)]
CARDS = os.getenv("CARDS", "1") == "1"  # kill switch: the card schema is not verified against ASI:One
EXAMPLES = {"name": "NAME Maria Lopez", "rate": "RATE 20", "employer": "EMPLOYER Big Retail Co",
            "title": "TITLE Cashier", "store": "STORE Westwood, Los Angeles", "manager": "MANAGER manager@example.com",
            "cover": "COVER yes yes yes"}
TEXT_FIELDS = {"NAME": "name", "EMPLOYER": "employer", "TITLE": "title", "STORE": "store"}
FOOTER = ("When did you get this schedule? If not today reply GOT YYYY-MM-DD. Fix with EDIT YYYY-MM-DD HH:MM-HH:MM "
          "or DROP YYYY-MM-DD. Then CONFIRM.")
QUESTIONS = {"employee_requested": "Did you ask for this change?",
             "voluntary_cover": "Did you volunteer to cover for a coworker?",
             "misconduct": "Was this cut for a disciplinary reason?"}
KIND_WORDS = {"added": "shift added", "cancelled": "shift cancelled", "hours_added": "hours added",
              "hours_cut": "hours cut", "moved": "shift moved", "moved_and_added": "shift moved and hours added",
              "moved_and_cut": "shift moved and hours cut", "needs_review": "change needs review"}
PAY_RULES = {"R2", "R3", "R4"}


def _today() -> date:
    return datetime.now(LA).date()


def _t(t: time) -> str:
    return f"{t.hour % 12 or 12}:{t.minute:02d} {'AM' if t.hour < 12 else 'PM'}"


def _d(d: date) -> str:
    return f"{d:%a %b} {d.day}"


def _shift(s: Shift) -> str:
    return f"{_d(s.day)} {_t(s.start)}-{_t(s.end)}" + (f" {s.location}" if s.location else "")


def usd(cents: int) -> str:
    return f"${cents // 100:,}.{cents % 100:02d}"


def _missing(data: dict) -> list[str]:
    return [k for k, _ in STEPS if not data.get(k)]


def _setup_prompt(missing: list[str]) -> str:
    example = "\n".join(EXAMPLES[k] for k, _ in STEPS if k in missing)
    return ("To set up, reply with:\n" + "\n".join(f"- {text}" for k, text in STEPS if k in missing)
            + "\n\nEach item starts with its keyword. Copy this, change the values, and send it:\n```\n"
            + example + "\n```")


MENTION = re.compile(r"^\s*(?:@\S+\s*)+")  # ASI:One puts "@agent1q... " in front of the text
KEYWORDS = r"NAME|RATE|EMPLOYER|TITLE|STORE|MANAGER|COVER|GOT|EDIT|DROP|CONFIRM|RECEIPT|SEND|HELP|RESET|OT|Q\d{1,3}"


def _normalize(text: str) -> str:
    """Strip mentions; split a one-line message into one command per line (chat apps often drop newlines)."""
    text = MENTION.sub("", text).strip()
    if "\n" in text:
        return text
    if text.upper().startswith("SCHEDULE "):
        return re.sub(r"\s+(?=\d{4}-\d{2}-\d{2}\b)", "\n", text)
    if len(re.findall(rf"(?<!\S)(?:{KEYWORDS})(?=\s|$)", text)) > 1:  # uppercase keywords only
        return re.sub(rf"\s+(?=(?:{KEYWORDS})(?:\s|$))", "\n", text)
    return text


def _sha_shifts(shifts: list[Shift]) -> str:
    return hashlib.sha256(schedule_text(sorted(shifts, key=lambda s: s.start_dt())).encode()).hexdigest()


def _pending(sender: str, data: dict):
    return next((v for v in db.versions(DB_PATH, sender, confirmed_only=False) if v.id == data.get("pending_vid")),
                None)


def _show(v, warnings: list[str] = ()) -> str:
    rows = [f"{i}. {_shift(s)}" for i, s in enumerate(sorted(v.shifts, key=lambda s: s.start_dt()), 1)]
    out = [f"Here is what I read (schedule {v.id}, got on {_d(v.learned_at.astimezone(LA).date())}):"]
    out += rows or ["(no shifts)"]
    out += [f"Skipped: {w}" for w in warnings if w != "unreadable"]
    return "\n".join(out + ["", FOOTER])


def _describe(e) -> str:
    what = KIND_WORDS[e.kind]
    if e.old and e.new:
        return f"{what} from {_shift(e.old)} to {_shift(e.new)}"
    return f"{what} ({_shift(e.old or e.new)})" if (e.old or e.new) else what


def _week(d: date):
    return d.isocalendar()[:2]


def _in_week(v, w):
    return v.model_copy(update={"shifts": [s for s in v.shifts if _week(s.day) == w]})


def _events(sender: str):
    """Each work week is compared only with earlier schedules that cover the same week."""
    # ponytail: a schedule with no shifts at all in a week cannot say "week cancelled"; screenshots never do
    vs = db.versions(DB_PATH, sender)
    covers = _covers(sender, vs)
    events = []
    for w in sorted(set().union(*covers.values()) if covers else set()):
        cover = [_in_week(v, w) for v in vs if w in covers[v.id]]
        events += [e for a, b in zip(cover, cover[1:]) for e in diff(a, b)]
    return vs, sorted(events, key=lambda e: (e.day, e.id))


def _covers(sender: str, vs) -> dict:
    """Weeks each version covers, as uploaded (saved then), so dropping every shift of a week still cancels it."""
    data, _ = db.get_profile(DB_PATH, sender)
    saved = data.get("weeks", {})
    return {v.id: {tuple(w) for w in saved.get(str(v.id), [])} | {_week(s.day) for s in v.shifts} for v in vs}


def _current_shifts(vs) -> list[Shift]:
    """Latest known shifts for every week (versions are in learned order)."""
    covers = _covers(vs[0].sender, vs) if vs else {}
    latest = {w: v for v in vs for w in covers[v.id]}
    return [s for w, v in latest.items() for s in v.shifts if _week(s.day) == w]


def _ask(events, qs: dict) -> str:
    by_id = {e.id: e for e in events}
    out = ["A few questions about each change. Reply to each, e.g. Q1 no."]
    for n, (eid, field) in qs.items():
        e = by_id.get(eid)
        out.append(f"Q{n} {_d(e.day)}, {_describe(e)}: {QUESTIONS[field]}" if e else f"Q{n} {QUESTIONS[field]}")
    return "\n".join(out)


def _open(sender: str, qs: dict) -> dict:
    answers = db.get_answers(DB_PATH, sender)
    return {n: q for n, q in qs.items() if getattr(answers.get(q[0], Answers()), q[1]) is None}


def _after_confirm(sender: str) -> list[str]:
    data, _ = db.get_profile(DB_PATH, sender)
    vs, events = _events(sender)
    missing = rules.missing_answers(events, db.get_answers(DB_PATH, sender))
    if not missing or not Coverage(**data["cover"]).covered():
        return receipt(sender)
    qs = {str(i): list(m) for i, m in enumerate(missing, 1)}
    db.update_profile(DB_PATH, sender, questions=qs)
    return [_ask(events, qs)]


def receipt(sender: str) -> list[str]:
    data, _ = db.get_profile(DB_PATH, sender)
    vs, events = _events(sender)
    if not vs:
        return ["No confirmed schedule yet. Send your schedule, then CONFIRM."]
    cov = Coverage(**data["cover"])
    ot = {date.fromisoformat(k): v for k, v in data.get("ot", {}).items()}
    lines = (rules.evaluate(events, db.get_answers(DB_PATH, sender), cov, data["rate"])
             + rules.rest_lines(_current_shifts(vs), cov, data["rate"], ot))
    by_id = {e.id: e for e in events}
    out, saved = ["Your schedule receipt:"], []
    if len(vs) == 1:
        out.append("This is your first schedule, so I saved it as a baseline. Only the rest rule applies until a "
                   "changed schedule arrives.")
    for l in lines:
        e = by_id.get(l.event_id)
        day = e.day if e else date.fromisoformat(l.event_id.removeprefix("rest-"))
        what = KIND_WORDS[e.kind] if e else "under 10 hours rest"
        status = ("may be owed" + (" if you work it" if l.rule == "R6" and day >= _today() else "")
                  if l.status == "may_be_owed" else f"{l.status.replace('_', ' ')}: {l.explanation}")
        out.append(f"{_d(day)} | {what} | {usd(l.cents)} | {status} | {l.citation}")
        saved.append({**l.model_dump(), "day": day.isoformat(), "change": what})
    if not lines:
        out.append("No changes found between your schedules.")
    sched, rest, tot = rules.total(lines, PAY_RULES), rules.total(lines, {"R6"}), rules.total(lines)
    out += [f"Schedule change pay that may be owed: {usd(sched)}"]
    if rest:
        out += [f"Rest premium that may be owed, only for shifts you actually work: {usd(rest)}"]
    out += [f"Estimated total: {usd(tot)}. This is an estimate, not unpaid wages yet: predictability pay is due on "
            "the payday for the pay period of the change.", rules.NOT_CHECKED, "Questions: OWS (844) 924-3752"]
    due = rules.due_lines(lines, datetime.now(LA), _current_shifts(vs))
    if due:
        # ponytail: a new pending notice per receipt; claim_notice's daily cap limits what can actually be sent
        keep = {l.event_id for l in due}
        due_saved = [s for s in saved if s["event_id"] in keep]
        nid = db.create_notice(DB_PATH, sender, due_saved, rules.total(due))
        db.update_profile(DB_PATH, sender, notice={"id": nid, "lines": due_saved, "day": _today().isoformat()})
        card = _card(nid, rules.total(due), data["manager"])
        out += ["", f"Notice preview ({nid}): {data['employer']} may owe {data['name']} {usd(rules.total(due))} "
                    "under the LA Fair Work Week Ordinance for:"]
        out += [f"- {s['day']} {s['change']}: {usd(s['cents'])}" for s in saved if s["event_id"] in keep]
        out += ["", "Check your paycheck for that pay period first. If the pay is missing, reply SEND "
                f"{nid} to email the official Notice to Cure to {data['manager']}. Your employer then has 15 days "
                "from receiving it to fix this."]
    elif tot:
        out += ["", "Nothing to claim yet: the rest premium is only owed once you work that shift. Reply RECEIPT "
                    "after you work it."]
    else:
        out += ["", "Nothing may be owed right now (the reason is on each line). Your saved schedules protect you "
                    "later: send every new schedule you get and I compare it with these."]
    return ["\n".join(out)] + ([card] if due and card else [])


def _card(nid: int, cents: int, manager: str) -> MetadataContent | None:
    """Interactive card with one button; the click comes back as {"action": "send", "receipt_id": "<id>"}."""
    if not CARDS:
        return None
    try:
        payload = {"title": "ShiftReceipt notice preview", "subtitle": f"{usd(cents)} may be owed",
                   "body": f"Check your paycheck first. If the pay is missing, send the Notice to Cure to {manager}. "
                           "Not legal advice.",
                   "cta": {"label": f"Send notice {nid}",
                           "selection": json.dumps({"action": "send", "receipt_id": str(nid)})}}
        return MetadataContent(type="metadata", metadata={
            "card_protocol_version": "1", "requires_card_interaction": "true", "card_kind": "custom",
            "card_payload": json.dumps(payload)})
    except Exception:
        return None


def _known(sender: str, sha: str) -> list[str] | None:
    """Reply for a schedule seen before: confirmed -> duplicate; unconfirmed -> bring it back up for review."""
    v = next((v for v in db.versions(DB_PATH, sender, confirmed_only=False) if v.sha256 == sha), None)
    if not v:
        return None
    if any(c.id == v.id for c in db.versions(DB_PATH, sender)):
        return ["Already have this one."]
    db.update_profile(DB_PATH, sender, pending_vid=v.id)
    data, _ = db.get_profile(DB_PATH, sender)
    return [_show(v)] if not _missing(data) else ["Already saved; I will show it once you are set up."]


def _new_version(sender: str, sha: str, shifts: list[Shift], warnings: list[str], typed: bool = False) -> list[str]:
    same = next((v for v in db.versions(DB_PATH, sender, confirmed_only=False) if v.sha256 == sha), None)
    if typed and same and _sha_shifts(same.shifts) != sha:  # that version was edited since: this one is new
        sha = hashlib.sha256(f"{sha}:after:{same.id}".encode()).hexdigest()
    if (known := _known(sender, sha)) is not None:
        return known
    vid, _ = db.add_version(DB_PATH, sender, sha, shifts)
    data, _ = db.get_profile(DB_PATH, sender)
    db.update_profile(DB_PATH, sender, pending_vid=vid,
                      weeks={**data.get("weeks", {}), str(vid): sorted({_week(s.day) for s in shifts})})
    data, _ = db.get_profile(DB_PATH, sender)
    if m := _missing(data):
        return ["Saved your schedule. I will show it once you are set up.\n" + _setup_prompt(m)]
    return [_show(_pending(sender, data), warnings)]


def handle_image(sender: str, data: bytes, mime: str) -> list[str]:
    sha = hashlib.sha256(data).hexdigest()
    if (known := _known(sender, sha)) is not None:
        return known
    if any(q[2] == sha for q in PENDING_IMAGES[sender]):
        return ["Already have this one."]
    profile, _ = db.get_profile(DB_PATH, sender)
    if not profile.get("name"):
        PENDING_IMAGES[sender].append((data, mime, sha))
        return ["I will read it once you are set up.\n" + _setup_prompt(_missing(profile))]
    shifts, warnings = extract(data, mime, profile["name"], _today())
    if not shifts:
        return [f"I could not read any shifts for {profile['name']} in that image. You can type your schedule "
                "instead:\n\n" + SCHEDULE_EXAMPLE]
    return _new_version(sender, sha, shifts, warnings)


def _saved(data: dict) -> str:
    """What is saved so far, so a wrong value is visible; resending that one line replaces it."""
    show = {"name": data.get("name"), "rate": data.get("rate") and usd(data["rate"]) + "/h",
            "employer": data.get("employer"), "title": data.get("title"), "store": data.get("store"),
            "manager": data.get("manager"),
            "cover": data.get("cover") and " ".join("yes" if v else "no" for v in data["cover"].values())}
    rows = [f"{k.upper()} {v}" for k, v in show.items() if v]
    return "Saved so far (send a line again to change it):\n" + "\n".join(rows) if rows else "Saved."


def _after_setup_field(sender: str, state: str) -> list[str]:
    data, _ = db.get_profile(DB_PATH, sender)
    read = []
    if data.get("name"):  # NAME known: read the waiting images now and save them as versions
        for img in PENDING_IMAGES.pop(sender, []):
            read += handle_image(sender, img[0], img[1])
        data, _ = db.get_profile(DB_PATH, sender)
    if m := _missing(data):
        return [_saved(data) + "\n\n" + _setup_prompt(m)]
    if state != "onboarding":
        return [_saved(data)] + read
    db.update_profile(DB_PATH, sender, state="ready")
    if v := _pending(sender, data):
        return [_saved(data) + "\n\nYou are set up.\n\n" + _show(v)]
    return [_saved(data) + "\n\nYou are set up. Send a screenshot of your schedule, or type it like this:\n\n" + SCHEDULE_EXAMPLE]


def run(sender: str, c) -> list[str]:
    data, state = db.get_profile(DB_PATH, sender)
    n, a = c.name, c.args
    if n == "HELP":
        return [HELP_TEXT]
    if n == "RESET":
        if sender not in DEMO_SENDERS:
            return ["RESET is only available on demo accounts."]
        db.reset(DB_PATH, sender)
        PENDING_IMAGES.pop(sender, None)
        return ["Reset done.\n" + _setup_prompt([k for k, _ in STEPS])]
    if n in TEXT_FIELDS:
        db.update_profile(DB_PATH, sender, notice=None, **{TEXT_FIELDS[n]: " ".join(a["value"].split())})
        return _after_setup_field(sender, state)
    if n in ("RATE", "MANAGER", "COVER"):
        db.update_profile(DB_PATH, sender, notice=None,  # a changed profile needs a fresh preview
                          **{"RATE": {"rate": a.get("cents")}, "MANAGER": {"manager": a.get("email")},
                             "COVER": {"cover": a}}[n])
        return _after_setup_field(sender, state)
    if n == "SCHEDULE":
        shifts = [Shift(**s) for s in a["shifts"]]
        if any(s.minutes() > 16 * 60 for s in shifts):
            return ["A shift longer than 16 hours looks like a typo. Please check and send it again."]
        return _new_version(sender, _sha_shifts(shifts), shifts, [], typed=True)
    if m := _missing(data):
        return [_setup_prompt(m)]
    if n in ("GOT", "EDIT", "DROP", "CONFIRM"):
        v = _pending(sender, data)
        if not v:
            return ["Nothing waiting to confirm. Send a schedule first."]
        if n == "CONFIRM":
            db.update_version(DB_PATH, sender, v.id, confirmed=True)
            db.update_profile(DB_PATH, sender, pending_vid=None)
            done = {c.id for c in db.versions(DB_PATH, sender)}
            left = [u.id for u in db.versions(DB_PATH, sender, confirmed_only=False) if u.id not in done]
            note = (f" Schedule(s) {', '.join(map(str, left))} are still unconfirmed: send them again to review."
                    if left else "")
            return ["Confirmed." + note] + _after_confirm(sender)
        if n == "GOT":
            if a["day"] > _today():
                return ["That date is in the future. Reply GOT with the date you got this schedule."]
            db.update_version(DB_PATH, sender, v.id, learned_at=datetime.combine(a["day"], time(9), LA))
        else:
            keep = [s for s in v.shifts if s.day != a["day"]]
            if n == "DROP" and len(keep) == len(v.shifts):
                return [f"No shift on {_d(a['day'])}."]
            if n == "EDIT":
                old = next((s for s in v.shifts if s.day == a["day"]), None)
                new = Shift(day=a["day"], start=a["start"], end=a["end"], location=old.location if old else None)
                if new.minutes() > 16 * 60:
                    return ["A shift longer than 16 hours looks like a typo. Please check and try again."]
                keep.append(new)
            db.update_version(DB_PATH, sender, v.id, shifts=sorted(keep, key=lambda s: s.start_dt()))
        return [_show(_pending(sender, data))]
    if n == "ANSWER":
        qs = data.get("questions", {})
        if str(a["q"]) not in qs:
            vs, events = _events(sender)
            still = _open(sender, qs)
            return [_ask(events, still) if still else "No open questions. Reply RECEIPT to see your receipt."]
        eid, field = qs[str(a["q"])]
        db.set_answer(DB_PATH, sender, eid, field, a["value"])
        still = _open(sender, qs)
        return [f"Saved. Still open: {', '.join('Q' + k for k in still)}."] if still else receipt(sender)
    if n == "RECEIPT":
        return receipt(sender)
    if n == "OT":
        db.update_profile(DB_PATH, sender, notice=None, ot={**data.get("ot", {}), a["day"].isoformat(): a["minutes"]})
        return [f"Saved {a['minutes']} overtime minutes on {_d(a['day'])}."]
    if n == "SEND":
        return send_notice(sender, a["id"])
    return [HELP_TEXT]


def welcome(sender: str) -> str:
    data, _ = db.get_profile(DB_PATH, sender)
    if m := _missing(data):
        return ("Hi, I am ShiftReceipt. I check LA Fair Work Week schedule changes and show what may be owed. "
                "Not legal advice.\n" + _setup_prompt(m))
    return "Welcome back. Send your newest schedule, or RECEIPT to see your receipt."


COMMANDS = ["SEND", "CONFIRM", "RECEIPT", "GOT", "EDIT", "DROP", "HELP", "SCHEDULE", "RESET", "OT", "NAME", "RATE",
            "EMPLOYER", "TITLE", "STORE", "MANAGER", "COVER"]


def _hint(sender: str, data: dict, text: str) -> str:
    """Unreadable text: say so, guess the command they meant, and point to the next step for where they are."""
    words = text.split()
    out = [f'I could not read "{text.strip()[:40]}".']
    guess = difflib.get_close_matches(words[0].upper(), COMMANDS, n=1, cutoff=0.6) if words else []
    if guess and guess[0] != words[0].upper():
        out.append(f"Did you mean: {' '.join([guess[0]] + words[1:])}")
    notice = data.get("notice") or {}
    still = _open(sender, data.get("questions", {}))
    if notice and text.strip() == str(notice.get("id")):
        out.append(f"To email notice {notice['id']}, type SEND {notice['id']}.")
    elif still:
        out.append(f"Open questions: {', '.join('Q' + k for k in still)}. Reply e.g. Q{next(iter(still))} no.")
    elif _pending(sender, data):
        out.append(FOOTER)
    elif notice:
        out.append(f"To email notice {notice['id']}, type SEND {notice['id']}. RECEIPT shows the receipt again.")
    else:
        out.append("Send a new schedule screenshot, or RECEIPT to see your receipt. HELP explains everything.")
    return "\n".join(out)


def _prose_send(text: str, c) -> list[str] | None:
    """Invariant 4: only a typed SEND <id> or a card click sends; prose like "do not send receipt 7" never does."""
    if c and c.name == "SEND" and not (_strict(text) or _from_json(text)):
        return [f"To email notice {c.args['id']}, type SEND {c.args['id']}."]
    return None


def handle_text(sender: str, text: str) -> list[str]:
    """One command per message, or one per line (pasted setup). Lines that are not commands are named back."""
    text = text or ""
    if len(text) > 2000:  # never truncate: a cut paste can change a value (RATE 200 -> RATE 20)
        return ["That message is too long (2000 characters max). Please send it in parts."]
    text = _normalize(text)
    lines = [l for l in text.splitlines() if l.strip()]
    if len(lines) > 1 and lines[0].strip().upper() != "SCHEDULE":
        cmds = [parse(l) for l in lines]
        if any(cmds):
            out = []
            for l, c in zip(lines, cmds):
                if c:
                    out = _prose_send(l, c) or run(sender, c)
            bad = [l.strip()[:60] for l, c in zip(lines, cmds) if not c]
            return out[:-1] + [out[-1] + "\n\nI could not read: " + "; ".join(bad)] if bad else out
    c = parse(text)
    if refused := _prose_send(text, c):
        return refused
    if not c:
        data, _ = db.get_profile(DB_PATH, sender)
        if m := _missing(data):
            return ["I could not read that.\n" + _setup_prompt(m)]
        return [_hint(sender, data, text)]
    return run(sender, c)


def send_notice(sender: str, nid: int) -> list[str]:
    """Only the latest notice preview, only for its owner, only once (db.claim_notice is atomic and capped)."""
    data, _ = db.get_profile(DB_PATH, sender)
    pending = data.get("notice") or {}
    if pending.get("id") == nid and pending.get("day") != _today().isoformat():
        return ["That preview is from an earlier day. Reply RECEIPT for a fresh one."]
    if pending.get("id") != nid or not db.claim_notice(DB_PATH, sender, nid):
        return ["That notice is not pending or the daily limit is reached."]
    now = datetime.now(LA)
    note = "Schedules: " + "; ".join(
        f"got {v.learned_at.astimezone(LA).date()} ({'worker-stated' if v.learned_source == 'worker' else 'upload date'})"
        f", uploaded {v.received_at.astimezone(LA).date()}" for v in db.versions(DB_PATH, sender)) + "."
    step = "pdf"
    try:
        pdf = notice.render_notice({**data, "schedule_note": note}, pending["lines"], now.date())
        step = "smtp"
        mid = notice.send(data["manager"], pdf, data["name"])
    except Exception as e:  # back to pending so the worker can retry; log the cause, never secrets or addresses
        db.finish_notice(DB_PATH, sender, nid, None)
        code = getattr(e, "smtp_code", "") or getattr(getattr(e, "response", None), "status_code", "")
        try:  # Resend's error name only (its message can contain an address, which is never logged)
            code = f"{code} {e.response.json().get('name', '')}".strip()
        except Exception:
            pass
        missing = [] if os.getenv("RESEND_API_KEY") else [k for k in ("SMTP_USER", "SMTP_APP_PASSWORD") if not os.getenv(k)]
        logging.getLogger("shiftreceipt").error(
            f"notice {nid} not sent: step={step} error={type(e).__name__} code={code} missing_env={missing}")
        return [f"Not sent. Try SEND {nid} again."]
    db.finish_notice(DB_PATH, sender, nid, mid)
    return [f"Sent {_t(now.time())} to {data['manager']}. Your employer has 15 calendar days from receiving it to "
            f"fix this (until {_d(rules.cure_deadline(now))} if they receive it today). If not, you can file a "
            "complaint with OWS: wagesla.lacity.gov/complaint. Not legal advice."]


chat = Protocol(spec=chat_protocol_spec)


@chat.on_message(ChatMessage)
async def on_chat(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(sender, ChatAcknowledgement(timestamp=_now(), acknowledged_msg_id=msg.msg_id))
    async with LOCKS[sender]:  # before dedupe: one sender's messages are handled in arrival order
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
        await reply(ctx, sender, await asyncio.to_thread(welcome, sender))
    elif isinstance(item, ResourceContent):
        url = image_url(item)
        res = item.resource if isinstance(item.resource, list) else [item.resource]
        ctx.logger.info(f"image: {len(res)} resource(s), mime hints {[r.metadata.get('mime_type') for r in res]}")
        try:
            if not url:
                raise DownloadError("no url")
            data, _mime = await asyncio.to_thread(download, url)
        except DownloadError as e:
            ctx.logger.info(f"image download failed: {e}")
            await reply(ctx, sender, FALLBACK_TEXT)
            return
        ctx.logger.info(f"image downloaded: {len(data) // 1024} KB {_mime}")
        await reply(ctx, sender, f"Got your schedule image ({max(1, round(len(data) / 1024))} KB). Reading it now.")
        for text in await asyncio.to_thread(handle_image, sender, data, _mime):
            await reply(ctx, sender, text)
    elif isinstance(item, TextContent):
        for text in await asyncio.to_thread(handle_text, sender, item.text):
            await reply(ctx, sender, text)


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
                  handle=os.getenv("AGENT_HANDLE") or None, avatar_url=os.getenv("AGENT_AVATAR_URL") or None,
                  publish_agent_details=True, handle_messages_concurrently=True)
    agent.include(chat, publish_manifest=True)

    @agent.on_event("startup")
    async def hello(ctx: Context):
        ctx.logger.info(f"Agent address: {agent.address}")
        ctx.logger.info("open the Agent Inspector link above, connect Mailbox")

    agent.run()


if __name__ == "__main__":
    main()
