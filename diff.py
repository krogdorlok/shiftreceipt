"""Compare two schedule versions and list every change, one event per affected shift."""
from collections import defaultdict

from models import ChangeEvent, Shift, ScheduleVersion

THRESHOLD = 15  # minutes


def _by_day(v: ScheduleVersion) -> dict:
    out = defaultdict(list)
    for s in v.shifts:
        out[s.day].append(s)
    return out


def _same_day_kind(old: Shift, new: Shift) -> str | None:
    delta = new.minutes() - old.minutes()
    moved = old.start != new.start or old.location != new.location
    if moved:
        if delta > THRESHOLD:
            return "moved_and_added"
        if delta <= -THRESHOLD:
            return "moved_and_cut"
        return "moved"
    if delta > THRESHOLD:
        return "hours_added"
    if delta <= -THRESHOLD:
        return "hours_cut"
    return None  # no change, or an end-time change below both thresholds


def diff(prev: ScheduleVersion, curr: ScheduleVersion) -> list[ChangeEvent]:
    p, c = _by_day(prev), _by_day(curr)
    events: list[ChangeEvent] = []

    def add(day, kind, old=None, new=None):
        delta = (new.minutes() if new else 0) - (old.minutes() if old else 0)
        events.append(ChangeEvent(id=f"{prev.id}-{curr.id}-{day}-{kind}", day=day, kind=kind,
                                  old=old, new=new, learned_at=curr.learned_at, minutes_delta=delta))

    days = sorted(set(p) | set(c))
    removed, added = [], []
    for d in days:
        olds, news = p.get(d, []), c.get(d, [])
        if len(olds) > 1 or len(news) > 1:
            if sorted(map(repr, olds)) != sorted(map(repr, news)):
                add(d, "needs_review")
        elif olds and news:
            kind = _same_day_kind(olds[0], news[0])
            if kind:
                add(d, kind, olds[0], news[0])
        elif olds:
            removed.append(olds[0])
        elif news:
            added.append(news[0])

    # A shift moved to another day in the same week is one "moved" event, not cancel + add, but only when the
    # pairing is certain: exactly one shift left the week and one arrived, same length.
    wk = lambda s: s.day.isocalendar()[:2]
    for w in {wk(o) for o in removed} & {wk(n) for n in added}:
        olds, news = [o for o in removed if wk(o) == w], [n for n in added if wk(n) == w]
        if len(olds) == len(news) == 1 and olds[0].minutes() == news[0].minutes():
            removed.remove(olds[0])
            added.remove(news[0])
            add(min(olds[0].day, news[0].day), "moved", olds[0], news[0])
    # Still both in one week: a move with new hours (FAQ: one change) or several moves. Any pairing is a guess
    # and cancel + add would overpay, so mark those days for review.
    both = {wk(o) for o in removed} & {wk(n) for n in added}
    for old in removed:
        add(old.day, "needs_review" if wk(old) in both else "cancelled", old=old)
    for new in added:
        add(new.day, "needs_review" if wk(new) in both else "added", new=new)
    return sorted(events, key=lambda e: (e.day, e.id))
