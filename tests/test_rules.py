from datetime import datetime

from conftest import NO_ANS, YES, S, V
from diff import diff
from models import LA, Answers, Coverage
import rules as R

RATE = 2000  # $20.00/h


def ev(a, b, learned="2026-10-18T09:00"):
    return diff(V(1, a), V(2, b, learned))


def one(a, b, ans=NO_ANS, cov=YES, rate=RATE, learned="2026-10-18T09:00"):
    events = ev(a, b, learned)
    return R.evaluate(events, {e.id: ans for e in events}, cov, rate)[0]


BASE = [S("2026-10-20", "09:00", "17:00")]


def test_moved_pays_one_hour():
    l = one(BASE, [S("2026-10-20", "13:00", "21:00")])
    assert (l.rule, l.cents, l.status) == ("R3", 2000, "may_be_owed")


def test_added_pays_one_hour():
    l = one(BASE, [S("2026-10-20", "09:00", "19:00")])
    assert (l.rule, l.cents) == ("R2", 2000)


def test_cut_pays_half_of_lost_hours():
    l = one(BASE, [S("2026-10-20", "09:00", "14:00")])
    assert (l.rule, l.cents) == ("R4", 3000)


def test_cancelled_pays_half_of_whole_shift():
    assert one(BASE, []).cents == 8000  # 8 h x $20 x 0.5


def test_rounding_half_up():
    l = one(BASE, [S("2026-10-20", "09:00", "16:45")], rate=1999)  # 1999 * 15 / 120 = 249.875
    assert l.cents == 250
    assert R.money(1, 30, 1, 2) == 0 and R.money(1, 60, 1, 2) == 1  # 0.25 -> 0, 0.5 -> 1


def test_fourteen_day_boundary():
    late = one(BASE, [S("2026-10-20", "13:00", "21:00")], learned="2026-10-07T23:59")  # 13 days
    ok = one(BASE, [S("2026-10-20", "13:00", "21:00")], learned="2026-10-06T00:01")    # 14 days
    assert late.status == "may_be_owed" and ok.status == "not_late" and ok.cents == 0


def test_lateness_uses_la_date_not_utc():
    from datetime import timezone
    e = ev(BASE, [S("2026-10-20", "13:00", "21:00")])[0]
    # 2026-10-07 03:00 UTC is still Oct 6 in LA: 14 days ahead, so not late
    assert R.is_late(e.model_copy(update={"learned_at": datetime(2026, 10, 7, 3, 0, tzinfo=timezone.utc)})) is False
    assert R.is_late(e.model_copy(update={"learned_at": datetime(2026, 10, 7, 9, 0, tzinfo=timezone.utc)})) is True


def test_coverage_blocks_all_amounts():
    for cov in (Coverage(), Coverage(retail=True, over_300=True, works_2h_la=False)):
        l = one(BASE, [], cov=cov)
        assert (l.status, l.cents) == ("not_covered", 0)


def test_unanswered_needs_answer():
    l = one(BASE, [], ans=Answers())
    assert (l.status, l.cents) == ("needs_answer", 0)


def test_missing_answers_lists_only_relevant_fields():
    events = ev(BASE, [S("2026-10-20", "09:00", "19:00")])
    assert R.missing_answers(events, {}) == [(events[0].id, "employee_requested"), (events[0].id, "voluntary_cover")]
    events = ev(BASE, [])
    assert R.missing_answers(events, {}) == [(events[0].id, "employee_requested"), (events[0].id, "misconduct")]
    assert R.missing_answers(ev(BASE, [S("2026-10-20", "13:00", "21:00")], "2026-10-01T09:00"), {}) == []  # not late


def test_exemptions():
    req = NO_ANS.model_copy(update={"employee_requested": True})
    assert one(BASE, [S("2026-10-20", "13:00", "21:00")], ans=req).status == "exempt"
    cover = NO_ANS.model_copy(update={"voluntary_cover": True})
    assert one(BASE, [S("2026-10-20", "09:00", "19:00")], ans=cover).status == "exempt"
    assert one(BASE, [], ans=cover).status == "may_be_owed"  # covering does not excuse a cut
    mis = NO_ANS.model_copy(update={"misconduct": True})
    assert one(BASE, [], ans=mis).status == "exempt"
    assert one(BASE, [S("2026-10-20", "09:00", "19:00")], ans=mis).status == "may_be_owed"


def test_already_paid():
    paid = NO_ANS.model_copy(update={"already_paid": True})
    l = one(BASE, [], ans=paid)
    assert (l.status, l.cents) == ("already_paid", 0)


def test_combined_change_needs_review():
    l = one(BASE, [S("2026-10-20", "10:00", "15:00")])
    assert (l.rule, l.status, l.cents) == ("REVIEW", "needs_review", 0)


def test_every_line_has_citation():
    events = ev(BASE + [S("2026-10-22", "09:00", "17:00")], [S("2026-10-20", "09:00", "19:00")])
    assert all(l.citation.startswith("OWS FWWO") for l in R.evaluate(events, {}, YES, RATE))


def test_evaluate_is_idempotent(demo):
    v1, v2, _ = demo
    events = diff(v1, v2)
    ans = {e.id: NO_ANS for e in events}
    assert R.evaluate(events, ans, YES, RATE) == R.evaluate(events, ans, YES, RATE)


def test_rest_boundaries():
    def rest(a_end, b_start):
        return R.rest_lines([S("2026-10-23", "16:00", a_end), S("2026-10-24", b_start, "14:00")], YES, RATE)
    assert rest("23:00", "09:00") == []                                   # exactly 10 h
    l = rest("23:00", "08:59")
    assert len(l) == 1 and l[0].status == "may_be_owed" and l[0].cents == R.money(RATE, 301, 1, 2)


def test_rest_split_shift_same_day_excluded():
    assert R.rest_lines([S("2026-10-23", "06:00", "10:00"), S("2026-10-23", "14:00", "18:00")], YES, RATE) == []


def test_rest_after_overnight_shift():
    l = R.rest_lines([S("2026-10-23", "22:00", "06:00"), S("2026-10-24", "14:00", "20:00")], YES, RATE)
    assert l[0].cents == 6000  # 8 h gap, 6 h shift x $20 x 0.5


def test_rest_subtracts_overtime_and_handles_overlap():
    shifts = [S("2026-10-23", "16:00", "23:00"), S("2026-10-24", "06:00", "14:00")]
    from datetime import date
    assert R.rest_lines(shifts, YES, RATE, {date(2026, 10, 24): 120})[0].cents == 6000
    over = R.rest_lines([S("2026-10-23", "16:00", "07:00"), S("2026-10-24", "06:00", "14:00")], YES, RATE)
    assert (over[0].status, over[0].cents) == ("needs_review", 0)
    assert R.rest_lines(shifts, Coverage(), RATE)[0].status == "not_covered"


def test_demo_receipt_matches_pitch(demo):
    v1, v2, v3 = demo
    events = diff(v1, v2)
    lines = R.evaluate(events, {e.id: NO_ANS for e in events}, YES, RATE) + R.rest_lines(v2.shifts, YES, RATE)
    assert [(l.rule, l.cents) for l in lines] == [("R3", 2000), ("R4", 3000), ("R2", 2000), ("R6", 8000)]
    assert R.total(lines) == 15000
    e3 = diff(v2, v3)
    assert R.evaluate(e3, {e3[0].id: NO_ANS}, YES, RATE)[0].cents == 8000  # Sunday 8 h cancelled


def test_total_counts_only_owed():
    lines = R.evaluate(ev(BASE, []), {}, YES, RATE)
    assert R.total(lines) == 0


def test_cure_deadline_la_time():
    assert str(R.cure_deadline(datetime(2026, 10, 18, 23, 30, tzinfo=LA))) == "2026-11-02"
    from datetime import timezone
    assert str(R.cure_deadline(datetime(2026, 10, 19, 5, 0, tzinfo=timezone.utc))) == "2026-11-02"  # 22:00 LA Oct 18
