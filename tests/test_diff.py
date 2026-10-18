from conftest import S, V
from diff import diff
from models import nearest_date
from datetime import date


def kinds(a, b):
    return [e.kind for e in diff(V(1, a), V(2, b))]


def test_no_change():
    assert kinds([S("2026-10-20", "09:00", "17:00")], [S("2026-10-20", "09:00", "17:00")]) == []


def test_moved_same_day_same_hours():
    assert kinds([S("2026-10-20", "09:00", "17:00")], [S("2026-10-20", "13:00", "21:00")]) == ["moved"]


def test_location_change_is_moved():
    assert kinds([S("2026-10-20", "09:00", "17:00", "A")], [S("2026-10-20", "09:00", "17:00", "B")]) == ["moved"]


def test_hours_added_threshold():
    base = [S("2026-10-20", "09:00", "17:00")]
    assert kinds(base, [S("2026-10-20", "09:00", "17:15")]) == []          # exactly 15: not more than 15
    assert kinds(base, [S("2026-10-20", "09:00", "17:16")]) == ["hours_added"]


def test_hours_cut_threshold():
    base = [S("2026-10-20", "09:00", "17:00")]
    assert kinds(base, [S("2026-10-20", "09:00", "16:46")]) == []          # 14 min cut
    assert kinds(base, [S("2026-10-20", "09:00", "16:45")]) == ["hours_cut"]  # 15 min cut counts


def test_moved_and_added_and_cut():
    base = [S("2026-10-20", "09:00", "17:00")]
    assert kinds(base, [S("2026-10-20", "10:00", "19:00")]) == ["moved_and_added"]
    assert kinds(base, [S("2026-10-20", "10:00", "15:00")]) == ["moved_and_cut"]


def test_cancelled_and_added():
    assert kinds([S("2026-10-20", "09:00", "17:00")], []) == ["cancelled"]
    assert kinds([], [S("2026-10-20", "09:00", "17:00")]) == ["added"]


def test_moved_to_other_day_same_week_is_one_event():
    ev = diff(V(1, [S("2026-10-20", "09:00", "17:00")]), V(2, [S("2026-10-22", "09:00", "17:00")]))
    assert [e.kind for e in ev] == ["moved"] and ev[0].day == date(2026, 10, 20)


def test_moved_to_other_day_new_hours_same_week_needs_review():
    assert kinds([S("2026-10-20", "09:00", "17:00")], [S("2026-10-22", "09:00", "14:00")]) == ["needs_review"] * 2


def test_moved_to_next_week_is_cancel_plus_add():
    assert sorted(kinds([S("2026-10-23", "09:00", "17:00")], [S("2026-10-27", "09:00", "17:00")])) == ["added", "cancelled"]


def test_two_shifts_one_day_needs_review():
    a = [S("2026-10-20", "09:00", "12:00"), S("2026-10-20", "14:00", "18:00")]
    assert kinds(a, [S("2026-10-20", "09:00", "18:00")]) == ["needs_review"]
    assert kinds(a, list(a)) == []  # unchanged multi-shift day is fine


def test_overnight_minutes():
    assert S("2026-10-23", "22:00", "06:00").minutes() == 480


def test_ids_unique_and_deterministic(demo):
    v1, v2, _ = demo
    a, b = diff(v1, v2), diff(v1, v2)
    assert [e.id for e in a] == [e.id for e in b]
    assert len({e.id for e in a}) == len(a)


def test_demo_diff(demo):
    v1, v2, v3 = demo
    assert [(str(e.day), e.kind) for e in diff(v1, v2)] == [
        ("2026-10-20", "moved"), ("2026-10-22", "hours_cut"), ("2026-10-25", "hours_added")]
    assert [e.kind for e in diff(v2, v3)] == ["cancelled"]


def test_nearest_date_year_wrap():
    assert nearest_date(1, 3, date(2026, 12, 28)) == date(2027, 1, 3)
    assert nearest_date(12, 30, date(2027, 1, 2)) == date(2026, 12, 30)
    assert nearest_date(10, 20, date(2026, 10, 18)) == date(2026, 10, 20)
    assert nearest_date(2, 29, date(2027, 3, 1)) == date(2028, 2, 29)


def test_two_days_with_moved_starts_in_one_week_need_review_end_only_changes_stay_priced():
    base = [S("2026-10-19", "09:00", "17:00"), S("2026-10-20", "09:00", "17:00"), S("2026-10-21", "09:00", "17:00")]
    new = [S("2026-10-19", "10:00", "17:00"), S("2026-10-20", "11:00", "17:00"), S("2026-10-21", "09:00", "13:00")]
    assert kinds(base, new) == ["needs_review", "needs_review", "hours_cut"]
