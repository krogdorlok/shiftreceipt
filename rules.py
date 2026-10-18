"""LA Fair Work Week rules. Pure functions, integer cents, no I/O, no model output."""
from datetime import date, datetime, timedelta

from models import LA, Answers, ChangeEvent, Coverage, LedgerLine, Shift

NOTICE_DAYS = 14   # Rule 4
REST_MINUTES = 600  # Rule 6: 10 hours
CURE_DAYS = 15     # Rule 10
ADDED = {"added", "hours_added", "moved_and_added"}
CUT = {"cancelled", "hours_cut", "moved_and_cut"}
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


def period_start(day: date) -> date:
    # ponytail: assumes Mon-Sun work periods; take the start date from the posted schedule if employers differ
    return day - timedelta(days=day.weekday())


def is_late(e: ChangeEvent) -> bool:
    """Notice is measured from the start of the Work Period, not from the changed shift (City FAQ 36, 50, 52)."""
    learned = e.learned_at.astimezone(LA).date()
    return (period_start(e.day) - learned).days < NOTICE_DAYS


def _loc_changed(old: Shift, new: Shift) -> bool:
    a, b = (old.location or "").strip().lower(), (new.location or "").strip().lower()
    return bool(a and b) and a != b


def changes(e: ChangeEvent) -> int:
    """Hours of pay for date, location and time changes (City FAQ predictability pay table).
    A time change counts only when the hours stay the same; otherwise the hours change is the time change."""
    if not (e.old and e.new):
        return 0
    n = (e.old.day != e.new.day) + _loc_changed(e.old, e.new)
    return n + (e.kind == "moved" and e.old.start != e.new.start)


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
        if e.kind == "needs_review" or not is_late(e):
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
        elif e.kind == "needs_review" or (e.kind == "moved" and not changes(e)):
            lines.append(_line(e, "REVIEW", 0, "needs_review", CITE_PAY, "Unclear change; review with OWS."))
        elif not is_late(e):
            lines.append(_line(e, rule, 0, "not_late", CITE_NOTICE, "Changed 14 or more days ahead."))
        elif any(getattr(a, f) is None for f in _required(e)):
            lines.append(_line(e, rule, 0, "needs_answer", CITE_EXEMPT, "Answer the questions first."))
        elif a.already_paid:
            lines.append(_line(e, rule, 0, "already_paid", CITE_PAY, "Already on your paycheck."))
        elif a.employee_requested or (e.kind in ADDED and a.voluntary_cover) or (e.kind in CUT and a.misconduct):
            lines.append(_line(e, rule, 0, "exempt", CITE_EXEMPT, "An exception applies."))
        elif e.kind in CUT:
            lost, n = -e.minutes_delta, changes(e)
            extra = f" plus {n} h of pay for {n} date/location change(s)" if n else ""
            lines.append(_line(e, rule, money(rate_cents, lost, 1, 2) + n * rate_cents, "may_be_owed", CITE_PAY,
                               f"{lost} min cut with under 14 days notice: half pay for hours not worked{extra}."))
        else:
            n = (e.kind in ADDED) + changes(e)
            why = "Hours added" if e.kind in ADDED else "Date, time or location changed"
            lines.append(_line(e, rule, n * rate_cents, "may_be_owed", CITE_PAY,
                               f"{why} with under 14 days notice: {n} h of pay (1 h per change)."))
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


def total(lines: list[LedgerLine], rules: set[str] | None = None) -> int:
    return sum(l.cents for l in lines if l.status == "may_be_owed" and (rules is None or l.rule in rules))


def due_lines(lines: list[LedgerLine], today: date) -> list[LedgerLine]:
    """Lines a notice may claim today: the rest premium only for a shift already past (owed only if worked)."""
    return [l for l in lines if l.status == "may_be_owed"
            and (l.rule != "R6" or date.fromisoformat(l.event_id.removeprefix("rest-")) < today)]


def cure_deadline(received_at: datetime) -> date:
    """15 days from the employer's receipt of the Notice to Cure, not from when it was sent."""
    return received_at.astimezone(LA).date() + timedelta(days=CURE_DAYS)
