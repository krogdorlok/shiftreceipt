import json
import sys
from datetime import date, datetime, time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from models import LA, Answers, Coverage, ScheduleVersion, Shift  # noqa: E402

YES = Coverage(retail=True, over_300=True, works_2h_la=True)
NO_ANS = Answers(employee_requested=False, voluntary_cover=False, misconduct=False, already_paid=False)


def S(day, start, end, loc="Westwood"):
    return Shift(day=date.fromisoformat(day), start=time.fromisoformat(start), end=time.fromisoformat(end), location=loc)


def V(vid, shifts, learned="2026-10-18T09:00", sender="u1"):
    t = datetime.fromisoformat(learned).replace(tzinfo=LA)
    return ScheduleVersion(id=vid, sender=sender, received_at=t, learned_at=t, sha256=f"h{vid}", shifts=shifts)


def fixture(name):
    return [Shift(**s) for s in json.loads((ROOT / "fixtures" / f"{name}.json").read_text())]


@pytest.fixture
def demo():
    return V(1, fixture("v1"), "2026-10-04T10:00"), V(2, fixture("v2"), "2026-10-18T09:00"), V(3, fixture("v3"), "2026-10-19T08:00")
