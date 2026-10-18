"""LA Fair Work Week rules. Pure functions, integer cents, no I/O, no model output."""
from datetime import date, datetime, timedelta

from models import LA, Answers, ChangeEvent, Coverage, LedgerLine, Shift

NOTICE_DAYS = 14   # Rule 4
REST_MINUTES = 600  # Rule 6: 10 hours
CURE_DAYS = 15     # Rule 10
ADDED = {"added", "hours_added", "moved_and_added"}
CUT = {"cancelled", "hours_cut"}
CITE_PAY = "OWS FWWO Rule 5 (predictability pay)"
CITE_EXEMPT = "OWS FWWO Rule 5.1, LAMC 185.06.B (exceptions)"
CITE_NOTICE = "OWS FWWO Rule 4 (14-day notice)"
CITE_REST = "OWS FWWO Rule 6 (right to rest)"
CITE_COVER = "OWS FWWO Rules 1(a), 2 (coverage)"
NOT_CHECKED = ("Not checked: good-faith estimate, additional-hours offers, on-call shifts, "
               "force majeure, filing deadlines, penalties. Not legal advice.")


def money(rate_cents: int, minutes: int, num: int, den: int) -> int:
    """rate x minutes/60 x num/den in cents, rounded half up, integers only."""
    x, d = rate_cents * minutes * num, 60 * den
    return (2 * x + d) // (2 * d)


def is_late(e: ChangeEvent) -> bool:
    learned = e.learned_at.astimezone(LA).date()
    return (e.day - learned).days < NOTICE_DAYS


def _required(e: ChangeEvent) -> list[str]:
    f = ["employee_requested"]
    if e.kind in ADDED:
        f.append("voluntary_cover")
    if e.kind in CUT:
        f.append("misconduct")
    return f


def missing_answers(events: list[ChangeEvent], answers: dict[str, Answers]) -> list[tuple[str, str]]:
    """(event_id, field) pairs the agent must still ask about, late payable events only."""
    out = []
    for e in events:
        if e.kind in ("needs_review", "moved_and_cut") or not is_late(e):
            continue
        a = answers.get(e.id, Answers())
        out += [(e.id, f) for f in _required(e) if getattr(a, f) is None]
    return out


def _line(e, rule, cents, status, cite, why) -> LedgerLine:
    return LedgerLine(event_id=e.id, rule=rule, cents=cents, status=status, citation=cite, explanation=why)


def evaluate(events: list[ChangeEvent], answers: dict[str, Answers], coverage: Coverage,
             rate_cents: int) -> list[LedgerLine]:
    lines = []
    for e in events:
        rule = "R2" if e.kind in ADDED else "R4" if e.kind in CUT else "R3"
        a = answers.get(e.id, Answers())
        if not coverage.covered():
            lines.append(_line(e, rule, 0, "not_covered", CITE_COVER, "Coverage not confirmed; check with OWS."))
        elif e.kind in ("needs_review", "moved_and_cut"):
            lines.append(_line(e, "REVIEW", 0, "needs_review", CITE_PAY, "Combined change; review with OWS."))
        elif not is_late(e):
            lines.append(_line(e, rule, 0, "not_late", CITE_NOTICE, "Changed 14 or more days ahead."))
        elif any(getattr(a, f) is None for f in _required(e)):
            lines.append(_line(e, rule, 0, "needs_answer", CITE_EXEMPT, "Answer the questions first."))
        elif a.already_paid:
            lines.append(_line(e, rule, 0, "already_paid", CITE_PAY, "Already on your paycheck."))
        elif a.employee_requested or (e.kind in ADDED and a.voluntary_cover) or (e.kind in CUT and a.misconduct):
            lines.append(_line(e, rule, 0, "exempt", CITE_EXEMPT, "An exception applies."))
        elif e.kind in CUT:
            lost = -e.minutes_delta
            lines.append(_line(e, rule, money(rate_cents, lost, 1, 2), "may_be_owed", CITE_PAY,
                               f"{lost} min cut with under 14 days notice: half pay for hours not worked."))
        else:
            why = "Hours added" if e.kind in ADDED else "Date, time or location changed"
            lines.append(_line(e, rule, rate_cents, "may_be_owed", CITE_PAY,
                               f"{why} with under 14 days notice: 1 hour of pay."))
    return lines


def rest_lines(shifts: list[Shift], coverage: Coverage, rate_cents: int,
               ot_minutes: dict[date, int] | None = None) -> list[LedgerLine]:
    """Shift starting under 10 h after the previous one: 1.5x for the whole shift, so 0.5x extra is owed."""
    ot_minutes = ot_minutes or {}
    out, s = [], sorted(shifts, key=lambda x: x.start_dt())
    for a, b in zip(s, s[1:]):
        if a.day == b.day:
            continue  # split shift in one workday is excluded
        gap = (b.start_dt() - a.end_dt()).total_seconds() / 60
        if gap >= REST_MINUTES:
            continue
        eid = f"rest-{b.day}"
        mk = lambda c, st, why: LedgerLine(event_id=eid, rule="R6" if st != "needs_review" else "REVIEW",
                                           cents=c, status=st, citation=CITE_REST, explanation=why)
        if not coverage.covered():
            out.append(mk(0, "not_covered", "Coverage not confirmed; check with OWS."))
        elif gap < 0:
            out.append(mk(0, "needs_review", "Shifts overlap; check the schedule."))
        else:
            mins = max(b.minutes() - ot_minutes.get(b.day, 0), 0)
            out.append(mk(money(rate_cents, mins, 1, 2), "may_be_owed",
                          f"Starts {int(gap // 60)}h{int(gap % 60):02d} after your last shift: "
                          f"whole shift at 1.5x, extra half pay if worked. Needs your written consent."))
    return out


def total(lines: list[LedgerLine]) -> int:
    return sum(l.cents for l in lines if l.status == "may_be_owed")


def cure_deadline(sent_at: datetime) -> date:
    return sent_at.astimezone(LA).date() + timedelta(days=CURE_DAYS)
