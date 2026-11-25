"""High- and low-activity periods (module 04), from Accepted transactions only.

Weekday activity is normalised by how many times each weekday occurs in the period: a 30-day
window can contain five Mondays and four Sundays, so raw totals would favour some weekdays.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

from app.contexts.ledger.domain.transaction import Transaction
from app.shared.domain.date_range import DateRange
from app.shared.domain.money import Money

MIN_ACCEPTED_FOR_PATTERN = 30
MIN_DAYS_FOR_PATTERN = 14  # every weekday occurs at least twice
EXTREMES = 3


@dataclass(frozen=True, slots=True)
class Bucket:
    accepted_count: int
    accepted_amount: Money


@dataclass(frozen=True, slots=True)
class WeekdayActivity:
    weekday: int  # 0 = Monday (ISO)
    occurrences: int  # days of this weekday inside the period
    total: Bucket
    average_amount_per_day: Money | None


@dataclass(frozen=True, slots=True)
class DayActivity:
    day: date
    total: Bucket


@dataclass(frozen=True, slots=True)
class HourActivity:
    hour: int
    total: Bucket


@dataclass(frozen=True, slots=True)
class ActivityProfile:
    period: DateRange
    accepted_count: int
    pattern_sufficient: bool
    weekdays: list[WeekdayActivity]
    hours: list[HourActivity]
    busiest_days: list[DayActivity]
    quietest_days: list[DayActivity]  # includes zero-activity days: silence is low activity
    peak_weekday: int | None
    quiet_weekday: int | None
    peak_hour: int | None


def _bucket(txs: list[Transaction]) -> Bucket:
    return Bucket(len(txs), Money.total(t.amount for t in txs))


def activity_profile(transactions: Iterable[Transaction], period: DateRange) -> ActivityProfile:
    accepted = [t for t in transactions if t.status.is_collected and period.contains(t.occurred_at)]

    days = [period.start + timedelta(days=i) for i in range(period.days)]
    by_day: dict[date, list[Transaction]] = {d: [] for d in days}
    for t in accepted:
        by_day[t.occurred_at.date()].append(t)
    day_rows = [DayActivity(d, _bucket(by_day[d])) for d in days]

    weekdays = []
    for wd in range(7):
        occurrences = sum(1 for d in days if d.weekday() == wd)
        txs = [t for t in accepted if t.occurred_at.weekday() == wd]
        total = _bucket(txs)
        weekdays.append(WeekdayActivity(wd, occurrences, total,
                                        total.accepted_amount.average_over(occurrences)))

    hours = [HourActivity(h, _bucket([t for t in accepted if t.occurred_at.hour == h]))
             for h in range(24)]

    sufficient = len(accepted) >= MIN_ACCEPTED_FOR_PATTERN and period.days >= MIN_DAYS_FOR_PATTERN
    ranked_wd = sorted((w for w in weekdays if w.average_amount_per_day is not None),
                       key=lambda w: (w.average_amount_per_day.centimes, w.weekday))
    by_amount = sorted(day_rows, key=lambda d: (d.total.accepted_amount.centimes, d.day))
    active_hours = [h for h in hours if h.total.accepted_count > 0]

    return ActivityProfile(
        period=period,
        accepted_count=len(accepted),
        pattern_sufficient=sufficient,
        weekdays=weekdays,
        hours=hours,
        busiest_days=sorted(by_amount[-EXTREMES:], key=lambda d: -d.total.accepted_amount.centimes),
        quietest_days=by_amount[:EXTREMES],
        peak_weekday=ranked_wd[-1].weekday if sufficient and ranked_wd else None,
        quiet_weekday=ranked_wd[0].weekday if sufficient and ranked_wd else None,
        peak_hour=(max(active_hours, key=lambda h: (h.total.accepted_count, -h.hour)).hour
                   if sufficient and active_hours else None),
    )
