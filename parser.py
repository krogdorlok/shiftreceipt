"""Turn a chat message (card click JSON, planner prose, or typed command) into one command."""
import json
import re
from datetime import date, time

from pydantic import BaseModel

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TIME = r"([01]?\d|2[0-3]):([0-5]\d)"


class Command(BaseModel):
    name: str
    args: dict = {}


def _yes(w: str) -> bool | None:
    return {"yes": True, "y": True, "no": False, "n": False}.get(w.lower())


def _schedule(t: str) -> Command | None:
    """SCHEDULE on line 1, then one shift per line: 2026-10-20 09:00-17:00 [location]."""
    lines = [l.strip() for l in t.strip().splitlines() if l.strip()]
    if not lines or lines[0].upper() != "SCHEDULE" or not 1 < len(lines) <= 40:
        return None
    shifts = []
    for l in lines[1:]:
        m = re.fullmatch(rf"(\S+)\s+{TIME}\s*-\s*{TIME}(?:\s+(.{{1,60}}))?", l)
        d = _date(m[1]) if m else None
        if not d or (m[2], m[3]) == (m[4], m[5]):
            return None
        shifts.append({"day": d, "start": time(int(m[2]), int(m[3])), "end": time(int(m[4]), int(m[5])),
                       "location": m[6]})
    return Command(name="SCHEDULE", args={"shifts": shifts})


def _strict(t: str) -> Command | None:
    parts = t.strip().split(maxsplit=1)
    if not parts:
        return None
    head, rest = parts[0].upper(), (parts[1].strip() if len(parts) > 1 else "")
    if head in ("HELP", "RESET", "RECEIPT", "CONFIRM") and not rest:
        return Command(name=head)
    if head == "RATE" and (m := re.fullmatch(r"\$?(\d{1,3})(?:\.(\d{2}))?", rest)):
        cents = int(m[1]) * 100 + int(m[2] or 0)
        return Command(name="RATE", args={"cents": cents}) if 0 < cents <= 20000 else None
    if head in ("NAME", "EMPLOYER", "TITLE", "STORE") and 0 < len(rest) <= 120:
        return Command(name=head, args={"value": rest})
    if head == "MANAGER" and EMAIL.match(rest):
        return Command(name="MANAGER", args={"email": rest.lower()})
    if head == "COVER" and len(w := rest.split()) == 3 and all(_yes(x) is not None for x in w):
        return Command(name="COVER", args=dict(zip(("retail", "over_300", "works_2h_la"), map(_yes, w))))
    if head in ("GOT", "DROP") and (d := _date(rest)):
        return Command(name=head, args={"day": d})
    if head == "EDIT" and (m := re.fullmatch(rf"(\S+)\s+{TIME}\s*-\s*{TIME}", rest)) and (d := _date(m[1])):
        s, e = time(int(m[2]), int(m[3])), time(int(m[4]), int(m[5]))
        return Command(name="EDIT", args={"day": d, "start": s, "end": e}) if s != e else None
    if head == "OT" and (m := re.fullmatch(r"(\S+)\s+(\d{1,3})", rest)) and (d := _date(m[1])):
        return Command(name="OT", args={"day": d, "minutes": int(m[2])}) if int(m[2]) <= 960 else None
    if head == "SEND" and re.fullmatch(r"\d{1,6}", rest):
        return Command(name="SEND", args={"id": int(rest)})
    if (m := re.fullmatch(r"Q(\d{1,3})", head)) and _yes(rest) is not None:
        return Command(name="ANSWER", args={"q": int(m[1]), "value": _yes(rest)})
    return None


def _date(s: str) -> date | None:
    try:
        return date.fromisoformat(s.strip())
    except ValueError:
        return None


def _from_json(t: str) -> Command | None:
    try:
        obj = json.loads(t)
    except (ValueError, TypeError):
        return None
    if not isinstance(obj, dict):
        return None
    act = str(obj.get("action", "")).lower()
    if act == "send" and str(obj.get("receipt_id", "")).isdigit():
        return Command(name="SEND", args={"id": int(obj["receipt_id"])})
    if act == "answer" and str(obj.get("q", "")).isdigit() and _yes(str(obj.get("value", ""))) is not None:
        return Command(name="ANSWER", args={"q": int(obj["q"]), "value": _yes(str(obj["value"]))})
    if act in ("confirm", "receipt", "help"):
        return Command(name=act.upper())
    return None


def _from_prose(t: str) -> Command | None:
    """Planner-relayed clicks: 'The user chose to send receipt 7'. Only unambiguous patterns."""
    low = t.lower()
    negated = re.search(r"\b(not|don't|dont|never|no)\b", low)
    if (m := re.search(r"\bsend\b\D{0,30}?(\d{1,6})\b", low)) and not negated:
        return Command(name="SEND", args={"id": int(m[1])})
    if (m := re.search(r"\bq(?:uestion)?\s*(\d{1,3})\b\D{0,20}?\b(yes|no)\b", low)):
        return Command(name="ANSWER", args={"q": int(m[1]), "value": m[2] == "yes"})
    if re.search(r"\bconfirm(ed|s)?\b", low) and not re.search(r"\b(not|don't|dont|no)\b", low):
        return Command(name="CONFIRM")
    return None


def parse(text: str) -> Command | None:
    t = (text or "").strip()[:2000]
    return _from_json(t) or _schedule(t) or _strict(t) or _from_prose(t)
