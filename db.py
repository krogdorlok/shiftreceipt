"""SQLite store. Every function takes `sender`; no query reads another user's rows."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from models import LA, Answers, ScheduleVersion, Shift

SCHEMA = """
CREATE TABLE IF NOT EXISTS profile(sender TEXT PRIMARY KEY, data TEXT NOT NULL DEFAULT '{}',
  state TEXT NOT NULL DEFAULT 'onboarding');
CREATE TABLE IF NOT EXISTS versions(id INTEGER PRIMARY KEY AUTOINCREMENT, sender TEXT NOT NULL,
  received_at TEXT NOT NULL, learned_at TEXT NOT NULL, learned_source TEXT NOT NULL, sha256 TEXT NOT NULL,
  shifts TEXT NOT NULL, confirmed INTEGER NOT NULL DEFAULT 0, UNIQUE(sender, sha256));
CREATE TABLE IF NOT EXISTS answers(sender TEXT NOT NULL, event_id TEXT NOT NULL, field TEXT NOT NULL,
  value INTEGER NOT NULL, PRIMARY KEY(sender, event_id, field));
CREATE TABLE IF NOT EXISTS seen(msg_id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS notices(id INTEGER PRIMARY KEY AUTOINCREMENT, sender TEXT NOT NULL,
  lines TEXT NOT NULL, total_cents INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
  message_id TEXT, created_at TEXT NOT NULL, sent_at TEXT);
"""
FIELDS = ("employee_requested", "voluntary_cover", "misconduct", "already_paid")
MAX_NOTICES_PER_DAY = 2


@contextmanager
def conn(path: str):
    c = sqlite3.connect(path, timeout=10, isolation_level=None)  # one connection per call: thread safe
    c.execute("PRAGMA journal_mode=WAL")
    try:
        yield c
    finally:
        c.close()


def init(path: str) -> None:
    with conn(path) as c:
        c.executescript(SCHEMA)


def first_time(path: str, msg_id: str) -> bool:
    """False if this message was already processed (duplicate delivery)."""
    with conn(path) as c:
        return c.execute("INSERT OR IGNORE INTO seen VALUES(?)", (msg_id,)).rowcount == 1


def get_profile(path: str, sender: str) -> tuple[dict, str]:
    with conn(path) as c:
        c.execute("INSERT OR IGNORE INTO profile(sender) VALUES(?)", (sender,))
        data, state = c.execute("SELECT data, state FROM profile WHERE sender=?", (sender,)).fetchone()
    return json.loads(data), state


def update_profile(path: str, sender: str, state: str | None = None, **fields) -> None:
    data, old_state = get_profile(path, sender)
    data.update(fields)
    with conn(path) as c:
        c.execute("UPDATE profile SET data=?, state=? WHERE sender=?", (json.dumps(data), state or old_state, sender))


def add_version(path: str, sender: str, sha256: str, shifts: list[Shift], learned_at: datetime | None = None
                ) -> tuple[int, bool]:
    """Returns (version id, is_new). Same image twice from the same sender is not a new version."""
    now = datetime.now(LA)
    with conn(path) as c:
        row = c.execute("SELECT id FROM versions WHERE sender=? AND sha256=?", (sender, sha256)).fetchone()
        if row:
            return row[0], False
        cur = c.execute("INSERT INTO versions(sender, received_at, learned_at, learned_source, sha256, shifts) "
                        "VALUES(?,?,?,?,?,?)", (sender, now.isoformat(), (learned_at or now).isoformat(),
                                                "worker" if learned_at else "upload", sha256,
                                                json.dumps([s.model_dump(mode="json") for s in shifts])))
        return cur.lastrowid, True


def update_version(path: str, sender: str, vid: int, shifts: list[Shift] | None = None,
                   learned_at: datetime | None = None, confirmed: bool | None = None) -> None:
    with conn(path) as c:
        if shifts is not None:
            c.execute("UPDATE versions SET shifts=? WHERE id=? AND sender=?",
                      (json.dumps([s.model_dump(mode="json") for s in shifts]), vid, sender))
        if learned_at is not None:
            c.execute("UPDATE versions SET learned_at=?, learned_source='worker' WHERE id=? AND sender=?",
                      (learned_at.isoformat(), vid, sender))
        if confirmed is not None:
            c.execute("UPDATE versions SET confirmed=? WHERE id=? AND sender=?", (int(confirmed), vid, sender))


def versions(path: str, sender: str, confirmed_only: bool = True) -> list[ScheduleVersion]:
    """Ordered by when the worker learned of each schedule, not by upload order."""
    q = "SELECT id, received_at, learned_at, learned_source, sha256, shifts FROM versions WHERE sender=?"
    q += " AND confirmed=1" if confirmed_only else ""
    with conn(path) as c:
        rows = c.execute(q + " ORDER BY learned_at, id", (sender,)).fetchall()
    return [ScheduleVersion(id=r[0], sender=sender, received_at=r[1], learned_at=r[2], learned_source=r[3],
                            sha256=r[4], shifts=[Shift(**s) for s in json.loads(r[5])]) for r in rows]


def set_answer(path: str, sender: str, event_id: str, field: str, value: bool) -> None:
    if field not in FIELDS:
        raise ValueError(field)
    with conn(path) as c:
        c.execute("INSERT OR REPLACE INTO answers VALUES(?,?,?,?)", (sender, event_id, field, int(value)))


def get_answers(path: str, sender: str) -> dict[str, Answers]:
    out: dict[str, dict] = {}
    with conn(path) as c:
        for eid, f, v in c.execute("SELECT event_id, field, value FROM answers WHERE sender=?", (sender,)):
            out.setdefault(eid, {})[f] = bool(v)
    return {k: Answers(**v) for k, v in out.items()}


def create_notice(path: str, sender: str, lines: list[dict], total_cents: int) -> int:
    with conn(path) as c:
        return c.execute("INSERT INTO notices(sender, lines, total_cents, created_at) VALUES(?,?,?,?)",
                         (sender, json.dumps(lines), total_cents, datetime.now(LA).isoformat())).lastrowid


def claim_notice(path: str, sender: str, nid: int) -> bool:
    """Atomic: only one caller can move a pending notice to sending. Enforces the daily cap."""
    today = datetime.now(LA).date().isoformat()
    with conn(path) as c:
        c.execute("BEGIN IMMEDIATE")
        sent = c.execute("SELECT COUNT(*) FROM notices WHERE sender=? AND status IN ('sending','sent') "
                         "AND substr(created_at,1,10)=?", (sender, today)).fetchone()[0]
        ok = sent < MAX_NOTICES_PER_DAY and c.execute(
            "UPDATE notices SET status='sending' WHERE id=? AND sender=? AND status='pending'",
            (nid, sender)).rowcount == 1
        c.execute("COMMIT")
        return ok


def finish_notice(path: str, sender: str, nid: int, message_id: str | None) -> None:
    """message_id None means the send failed: back to pending so the worker can retry."""
    with conn(path) as c:
        if message_id:
            c.execute("UPDATE notices SET status='sent', message_id=?, sent_at=? WHERE id=? AND sender=?",
                      (message_id, datetime.now(LA).isoformat(), nid, sender))
        else:
            c.execute("UPDATE notices SET status='pending' WHERE id=? AND sender=? AND status='sending'", (nid, sender))


def reset(path: str, sender: str) -> None:
    with conn(path) as c:
        for t in ("profile", "versions", "answers", "notices"):
            c.execute(f"DELETE FROM {t} WHERE sender=?", (sender,))
