"""Merchant Pulse: a short, evidence-based brief. Deterministic rules over stored metrics, no AI.

Every item follows: observation -> supporting metric -> comparison baseline -> financial relevance
-> suggested next check (a ledger filter). Every number is a Fact carried as an exact string; the
UI formats it into a translated sentence and never computes. When data is insufficient the item
says so instead of guessing.
"""

from __future__ import annotations

import calendar
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum

from app.contexts.analytics.domain.decline_signal import Verdict, decline_radar
from app.contexts.analytics.domain.kpis import compute_kpis
from app.contexts.analytics.domain.period_comparison import ChangeKind, compare
from app.contexts.ledger.domain.transaction import Transaction
from app.shared.domain.date_range import DateRange
from app.shared.domain.money import Money

MATERIAL_CHANGE = Decimal("0.05")  # below +-5% a collection change is reported as "stable"
CONCENTRATION_SHARE = Decimal("0.5")  # one channel holding >= 50% of declined value is noted


class FactKind(StrEnum):
    MONEY = "money"  # exact decimal string, DZD
    COUNT = "count"
    RATIO = "ratio"  # signed fraction, e.g. "-0.5088" = -50.88 %
    PROBABILITY = "probability"
    DATE = "date"
    CODE = "code"  # enum-like token the UI translates (channel, verdict, driver)


@dataclass(frozen=True, slots=True)
class Fact:
    kind: FactKind
    value: str | None  # None = not computable (e.g. a ratio against zero)


class Tone(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    INFO = "info"


class PulseCode(StrEnum):
    COLLECTION_UP = "collection_up"
    COLLECTION_DOWN = "collection_down"
    COLLECTION_STABLE = "collection_stable"
    COLLECTION_NEW = "collection_new"
    NO_ACTIVITY = "no_activity"
    COLLECTION_DRIVERS = "collection_drivers"
    DECLINES = "declines"
    GOAL_REACHED = "goal_reached"
    GOAL_ON_TRACK = "goal_on_track"
    GOAL_BEHIND = "goal_behind"
    GOAL_NOT_SET = "goal_not_set"


@dataclass(frozen=True, slots=True)
class PulseItem:
    code: PulseCode
    tone: Tone
    facts: dict[str, Fact] = field(default_factory=dict)
    evidence: str | None = None  # ledger query string for "see the transactions"


def _money(m: Money) -> Fact:
    return Fact(FactKind.MONEY, str(m.to_decimal()))


def _count(n: int) -> Fact:
    return Fact(FactKind.COUNT, str(n))


def _ratio(v: Decimal | None) -> Fact:
    return Fact(FactKind.RATIO, None if v is None else str(v.quantize(Decimal("0.0001"))))


def _evidence(period: DateRange, status: str, channel: str | None = None) -> str:
    q = f"status={status}&date_from={period.start}&date_to={period.last_day}"
    return q + (f"&channel={channel}" if channel else "")


def _collection_items(cur: list[Transaction], prev: list[Transaction],
                      period: DateRange) -> list[PulseItem]:
    k, p = compute_kpis(cur), compute_kpis(prev)
    change = compare(k.gross_collected.centimes, p.gross_collected.centimes)
    facts = {"current": _money(k.gross_collected), "previous": _money(p.gross_collected),
             "delta": _money(k.gross_collected - p.gross_collected), "change": _ratio(change.pct),
             "accepted_count": _count(k.accepted_count)}
    if change.kind is ChangeKind.NO_ACTIVITY:
        return [PulseItem(PulseCode.NO_ACTIVITY, Tone.INFO, facts)]
    if change.kind is ChangeKind.NEW_ACTIVITY:
        return [PulseItem(PulseCode.COLLECTION_NEW, Tone.POSITIVE, facts, _evidence(period, "accepted"))]
    if change.pct <= -MATERIAL_CHANGE:
        code, tone = PulseCode.COLLECTION_DOWN, Tone.NEGATIVE
    elif change.pct >= MATERIAL_CHANGE:
        code, tone = PulseCode.COLLECTION_UP, Tone.POSITIVE
    else:
        code, tone = PulseCode.COLLECTION_STABLE, Tone.NEUTRAL
    items = [PulseItem(code, tone, facts, _evidence(period, "accepted"))]

    # Exact decomposition: delta = (n1 - n0) * t0 + n1 * (t1 - t0) = volume effect + ticket effect.
    n0, n1 = p.accepted_count, k.accepted_count
    if n0 > 0 and n1 > 0 and change.delta != 0:
        volume = p.gross_collected.scale(Decimal(n1 - n0) / Decimal(n0))
        ticket = (k.gross_collected - p.gross_collected) - volume  # remainder: sums exactly
        driver = "volume" if abs(volume.centimes) >= abs(ticket.centimes) else "ticket"
        items.append(PulseItem(PulseCode.COLLECTION_DRIVERS, Tone.NEUTRAL, {
            "count_current": _count(n1), "count_previous": _count(n0),
            "ticket_current": _money(k.average_ticket), "ticket_previous": _money(p.average_ticket),
            "volume_effect": _money(volume), "ticket_effect": _money(ticket),
            "driver": Fact(FactKind.CODE, driver),
        }, _evidence(period, "accepted")))
    return items


def _decline_item(cur: list[Transaction], prev: list[Transaction], period: DateRange) -> PulseItem | None:
    overall, channels = decline_radar(cur, prev)
    c = overall.current
    if c.observed.denominator == 0:
        return None
    tone = {Verdict.ELEVATED: Tone.NEGATIVE, Verdict.LOWER: Tone.POSITIVE,
            Verdict.NO_CLEAR_CHANGE: Tone.NEUTRAL, Verdict.INSUFFICIENT_DATA: Tone.INFO}[overall.verdict]
    facts = {
        "declined_amount": _money(c.declined_amount),
        "declined": _count(c.observed.numerator), "attempts": _count(c.observed.denominator),
        "rate": _ratio(c.observed.value),
        "previous_rate": _ratio(overall.previous.observed.value),
        "previous_attempts": _count(overall.previous.observed.denominator),
        "probability_higher": Fact(FactKind.PROBABILITY, f"{overall.probability_higher:.4f}"),
        "verdict": Fact(FactKind.CODE, overall.verdict.value),
    }
    top = channels[0]
    evidence = _evidence(period, "declined")
    if c.declined_amount.centimes > 0:
        share = Decimal(top.current.declined_amount.centimes) / Decimal(c.declined_amount.centimes)
        if share >= CONCENTRATION_SHARE:
            facts |= {"top_channel": Fact(FactKind.CODE, top.channel.value),
                      "top_share": _ratio(share),
                      "top_amount": _money(top.current.declined_amount),
                      "top_attempts": _count(top.current.observed.denominator),
                      "top_verdict": Fact(FactKind.CODE, top.verdict.value)}
            evidence = _evidence(period, "declined", top.channel.value)
    return PulseItem(PulseCode.DECLINES, tone, facts, evidence)


def _goal_item(month_to_date: list[Transaction], goal: Money | None, today: date) -> PulseItem:
    if goal is None or goal.centimes <= 0:
        return PulseItem(PulseCode.GOAL_NOT_SET, Tone.INFO)
    month = DateRange.inclusive(today.replace(day=1), today)
    collected = compute_kpis(t for t in month_to_date if month.contains(t.occurred_at)).gross_collected
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    elapsed, left = today.day, days_in_month - today.day
    expected = goal.scale(Decimal(elapsed) / Decimal(days_in_month))  # linear pace
    remaining = goal - collected if collected.centimes < goal.centimes else Money.zero()
    facts = {
        "goal": _money(goal), "collected": _money(collected), "expected_by_now": _money(expected),
        "progress": _ratio(Decimal(collected.centimes) / Decimal(goal.centimes)),
        "remaining": _money(remaining), "days_left": _count(left),
        "daily_needed": _money(remaining.scale(Decimal(1) / Decimal(left))) if left > 0 and remaining.centimes
        else Fact(FactKind.MONEY, None),
        "month_start": Fact(FactKind.DATE, month.start.isoformat()),
        "as_of": Fact(FactKind.DATE, today.isoformat()),
    }
    if collected.centimes >= goal.centimes:
        code, tone = PulseCode.GOAL_REACHED, Tone.POSITIVE
    elif collected.centimes >= expected.centimes:
        code, tone = PulseCode.GOAL_ON_TRACK, Tone.POSITIVE
    else:
        code, tone = PulseCode.GOAL_BEHIND, Tone.NEGATIVE
    return PulseItem(code, tone, facts, _evidence(month, "accepted"))


def build_pulse(current: Iterable[Transaction], previous: Iterable[Transaction], period: DateRange,
                month_to_date: Iterable[Transaction], goal: Money | None, today: date) -> list[PulseItem]:
    cur, prev = list(current), list(previous)
    items = _collection_items(cur, prev, period)
    decline = _decline_item(cur, prev, period)
    if decline is not None:
        items.append(decline)
    items.append(_goal_item(list(month_to_date), goal, today))
    return items
