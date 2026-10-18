"""Frozen data contracts. Everyone imports these; change only with team agreement."""
from datetime import date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel

LA = ZoneInfo("America/Los_Angeles")

Kind = Literal["added", "cancelled", "hours_added", "hours_cut", "moved",
               "moved_and_added", "moved_and_cut", "needs_review"]
Status = Literal["may_be_owed", "exempt", "not_late", "needs_answer",
                 "needs_review", "not_covered", "already_paid"]


class Shift(BaseModel):
    day: date
    start: time
    end: time  # end <= start means the shift ends the next day
    location: str | None = None

    def start_dt(self) -> datetime:
        return datetime.combine(self.day, self.start, LA)

    def end_dt(self) -> datetime:
        end = datetime.combine(self.day, self.end, LA)
        return end + timedelta(days=1) if self.end <= self.start else end

    def minutes(self) -> int:
        return int((self.end_dt() - self.start_dt()).total_seconds() // 60)


class ScheduleVersion(BaseModel):
    id: int
    sender: str
    received_at: datetime  # server clock, tz-aware
    learned_at: datetime  # when the worker got this schedule
    learned_source: Literal["worker", "upload"] = "upload"
    sha256: str
    shifts: list[Shift]


class ChangeEvent(BaseModel):
    id: str
    day: date  # earliest affected shift date, used for the 14-day test
    kind: Kind
    old: Shift | None = None
    new: Shift | None = None
    learned_at: datetime
    minutes_delta: int = 0


class Answers(BaseModel):
    employee_requested: bool | None = None
    voluntary_cover: bool | None = None
    misconduct: bool | None = None
    already_paid: bool | None = None


class Coverage(BaseModel):
    retail: bool | None = None
    over_300: bool | None = None
    works_2h_la: bool | None = None

    def covered(self) -> bool:
        return self.retail is True and self.over_300 is True and self.works_2h_la is True


class LedgerLine(BaseModel):
    event_id: str
    rule: Literal["R2", "R3", "R4", "R6", "REVIEW"]
    cents: int
    status: Status
    citation: str
    explanation: str


def nearest_date(month: int, day: int, ref: date) -> date:
    """Screenshots rarely show the year: pick the year that puts the date closest to ref."""
    options = []
    for y in (ref.year - 1, ref.year, ref.year + 1):
        try:
            options.append(date(y, month, day))
        except ValueError:  # Feb 29 in a non-leap year
            pass
    return min(options, key=lambda d: abs((d - ref).days))
