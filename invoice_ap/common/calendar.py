"""Business-day calendar (weekends plus policy holidays). Pure date arithmetic, no business rules,
so both the oracle and the engine may use it."""
from __future__ import annotations

from datetime import date, timedelta

WEEKDAY_CODES = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")


class BusinessCalendar:
    def __init__(self, weekend: tuple[str, ...] = ("SAT", "SUN"), holidays: tuple[date, ...] = ()):
        self.weekend = frozenset(WEEKDAY_CODES.index(code) for code in weekend)
        self.holidays = frozenset(holidays)

    @classmethod
    def from_policy(cls, raw: dict) -> "BusinessCalendar":
        cal = raw["calendar"]
        return cls(tuple(cal["weekend"]), tuple(date.fromisoformat(h) for h in cal["holidays"]))

    def is_business_day(self, d: date) -> bool:
        return d.weekday() not in self.weekend and d not in self.holidays

    def next_business_day(self, d: date, include_today: bool = False) -> date:
        d = d if include_today else d + timedelta(days=1)
        while not self.is_business_day(d):
            d += timedelta(days=1)
        return d

    def previous_business_day(self, d: date, include_today: bool = False) -> date:
        d = d if include_today else d - timedelta(days=1)
        while not self.is_business_day(d):
            d -= timedelta(days=1)
        return d

    def add_business_days(self, d: date, n: int) -> date:
        """n business days after d (n = 0 returns d itself, rolled forward if not a business day)."""
        if n < 0:
            raise ValueError("n must be >= 0")
        d = self.next_business_day(d, include_today=True)
        for _ in range(n):
            d = self.next_business_day(d)
        return d

    def business_days(self, start: date, end: date) -> list[date]:
        """All business days in [start, end], in order."""
        out, d = [], start
        while d <= end:
            if self.is_business_day(d):
                out.append(d)
            d += timedelta(days=1)
        return out
