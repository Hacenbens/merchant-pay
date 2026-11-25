"""Customer loyalty intelligence: pseudonymous profiles, RFM measures and explainable segments.

Only ACCEPTED transactions that carry a customer_token are used. Refunds are not linked to their
original sale in this data, so they are NOT subtracted from a customer's value (documented rule).

Definitions (observation window W = [as_of - window_days + 1, as_of], rules version segments-v1):
- recency R    = days from the last accepted purchase to as_of (all history up to as_of)
- frequency F  = accepted transactions inside W
- monetary M   = accepted value inside W ("historical accepted value": not profit, not lifetime value)
- eligible     = customers with F >= 1
- repeat rate  = eligible customers with F >= 2 / eligible customers

Lifecycle segment (exactly one per eligible customer, evaluated in this order):
  NEW       one accepted purchase ever, made within new_days
  ONE_TIME  one accepted purchase ever, older than new_days (never returned)
  LAPSED    win-back status lapsed
  AT_RISK   win-back status at_risk
  LOYAL     F >= loyal_min_tx and first-to-last purchase span in W >= loyal_min_span_days
  ACTIVE    any other repeat customer
High value is a separate FLAG, never a segment (high spend is not loyalty): M strictly above the
high_value_quantile (nearest rank) of eligible customers' M. "Strictly" keeps ties at the threshold
from inflating the group. It is null when there are too few customers for a meaningful quantile.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum

from app.contexts.customers.domain.winback import (
    Baseline,
    ReturnEvidence,
    ReturnStatus,
    WinbackRules,
    pooled_baseline,
    return_status,
)
from app.contexts.ledger.domain.transaction import Transaction
from app.shared.domain.date_range import DateRange
from app.shared.domain.enums import TransactionStatus
from app.shared.domain.money import Money
from app.shared.domain.rate import Rate


@dataclass(frozen=True, slots=True)
class SegmentRules:
    version: str = "segments-v1"
    window_days: int = 180
    new_days: int = 30
    loyal_min_tx: int = 4
    loyal_min_span_days: int = 60
    high_value_quantile: Decimal = Decimal("0.8")
    min_customers: int = 20  # below this, customer analytics are "insufficient history"


class Segment(StrEnum):
    NEW = "new"
    ONE_TIME = "one_time"
    ACTIVE = "active"
    LOYAL = "loyal"
    AT_RISK = "at_risk"
    LAPSED = "lapsed"


class Availability(StrEnum):
    AVAILABLE = "available"
    NO_CUSTOMER_IDENTIFIER = "no_customer_identifier"
    INSUFFICIENT_HISTORY = "insufficient_history"


@dataclass(frozen=True, slots=True)
class Purchase:
    transaction_id: str
    day: date
    amount: Money


@dataclass(frozen=True, slots=True)
class CustomerProfile:
    token: str
    first_purchase: date
    last_purchase: date
    lifetime_purchases: int  # accepted transactions, all history up to as_of
    recency_days: int
    frequency: int  # accepted transactions in the window
    monetary: Money  # accepted value in the window
    segment: Segment
    high_value: bool | None
    evidence: ReturnEvidence

    @property
    def alias(self) -> str:
        return f"••••{self.token[-4:].upper()}"


@dataclass(frozen=True, slots=True)
class Coverage:
    accepted_in_window: int
    tokenised_in_window: int
    accepted_value_in_window: Money
    tokenised_value_in_window: Money

    @property
    def share(self) -> Rate:
        return Rate(self.tokenised_in_window, self.accepted_in_window)


@dataclass(frozen=True, slots=True)
class CustomerBook:
    as_of: date
    window: DateRange
    rules: SegmentRules
    winback_rules: WinbackRules
    availability: Availability
    coverage: Coverage
    pooled_baseline: Baseline | None
    high_value_threshold: Money | None
    profiles: list[CustomerProfile]  # eligible customers only, token order


def mask(token: str) -> str:
    return f"••••{token[-4:].upper()}"


def _quantile_threshold(values: list[int], q: Decimal) -> int:
    """Nearest-rank quantile on integer centimes (no interpolation, reproducible)."""
    ordered = sorted(values)
    rank = max(1, math.ceil(q * len(ordered)))
    return ordered[rank - 1]


def build_book(transactions: Iterable[Transaction], as_of: date,
               rules: SegmentRules = SegmentRules(),
               winback_rules: WinbackRules = WinbackRules()) -> CustomerBook:
    window = DateRange(as_of - timedelta(days=rules.window_days - 1), as_of + timedelta(days=1))
    accepted = [t for t in transactions
                if t.status is TransactionStatus.ACCEPTED and t.occurred_at.date() <= as_of]
    in_window = [t for t in accepted if window.contains(t.occurred_at)]
    tokenised_window = [t for t in in_window if t.customer_token]
    coverage = Coverage(len(in_window), len(tokenised_window),
                        Money.total(t.amount for t in in_window),
                        Money.total(t.amount for t in tokenised_window))

    by_customer: dict[str, list[Purchase]] = defaultdict(list)
    for t in accepted:
        if t.customer_token:
            by_customer[t.customer_token].append(Purchase(t.transaction_id, t.occurred_at.date(), t.amount))

    eligible = {tok: ps for tok, ps in by_customer.items() if any(window.contains(p.day) for p in ps)}
    if not by_customer:
        availability = Availability.NO_CUSTOMER_IDENTIFIER
    elif len(eligible) < rules.min_customers:
        availability = Availability.INSUFFICIENT_HISTORY
    else:
        availability = Availability.AVAILABLE

    pooled = pooled_baseline([[p.day for p in ps] for ps in by_customer.values()], winback_rules)
    monetary = {tok: Money.total(p.amount for p in ps if window.contains(p.day))
                for tok, ps in eligible.items()}
    hv_threshold = (Money(_quantile_threshold([m.centimes for m in monetary.values()],
                                              rules.high_value_quantile))
                    if len(eligible) >= rules.min_customers else None)

    profiles = []
    for tok in sorted(eligible):
        ps = sorted(eligible[tok], key=lambda p: p.day)
        days = [p.day for p in ps]
        window_ps = [p for p in ps if window.contains(p.day)]
        evidence = return_status(days, as_of, pooled, winback_rules)
        span = (window_ps[-1].day - window_ps[0].day).days
        if len(ps) == 1:
            segment = Segment.NEW if (as_of - ps[0].day).days < rules.new_days else Segment.ONE_TIME
        elif evidence.status is ReturnStatus.LAPSED:
            segment = Segment.LAPSED
        elif evidence.status is ReturnStatus.AT_RISK:
            segment = Segment.AT_RISK
        elif len(window_ps) >= rules.loyal_min_tx and span >= rules.loyal_min_span_days:
            segment = Segment.LOYAL
        else:
            segment = Segment.ACTIVE
        profiles.append(CustomerProfile(
            token=tok, first_purchase=days[0], last_purchase=days[-1], lifetime_purchases=len(ps),
            recency_days=(as_of - days[-1]).days, frequency=len(window_ps), monetary=monetary[tok],
            segment=segment,
            high_value=(monetary[tok].centimes > hv_threshold.centimes) if hv_threshold else None,
            evidence=evidence,
        ))
    return CustomerBook(as_of, window, rules, winback_rules, availability, coverage, pooled,
                        hv_threshold, profiles)


# ---- merchant-level summaries ----------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class GroupTotal:
    customers: int
    transactions: int
    accepted_value: Money  # historical accepted value inside the window


def _group(profiles: list[CustomerProfile]) -> GroupTotal:
    return GroupTotal(len(profiles), sum(p.frequency for p in profiles),
                      Money.total(p.monetary for p in profiles))


def by_segment(book: CustomerBook) -> dict[Segment, GroupTotal]:
    return {s: _group([p for p in book.profiles if p.segment is s]) for s in Segment}


def by_status(book: CustomerBook) -> dict[ReturnStatus, GroupTotal]:
    return {s: _group([p for p in book.profiles if p.evidence.status is s]) for s in ReturnStatus}


def repeat_rate(book: CustomerBook) -> Rate:
    return Rate(sum(1 for p in book.profiles if p.frequency >= 2), len(book.profiles))


@dataclass(frozen=True, slots=True)
class NewVsReturning:
    period: DateRange
    new: GroupTotal  # first-ever accepted purchase inside the period
    returning: GroupTotal  # bought before the period AND again inside it


def new_vs_returning(transactions: Iterable[Transaction], period: DateRange) -> NewVsReturning:
    first_seen: dict[str, date] = {}
    in_period: dict[str, list[Transaction]] = defaultdict(list)
    for t in sorted(transactions, key=lambda t: t.occurred_at):
        if t.status is not TransactionStatus.ACCEPTED or not t.customer_token:
            continue
        if t.occurred_at.date() >= period.end:
            continue
        first_seen.setdefault(t.customer_token, t.occurred_at.date())
        if period.contains(t.occurred_at):
            in_period[t.customer_token].append(t)

    def total(tokens: list[str]) -> GroupTotal:
        txs = [t for tok in tokens for t in in_period[tok]]
        return GroupTotal(len(tokens), len(txs), Money.total(t.amount for t in txs))

    new = [tok for tok in in_period if first_seen[tok] >= period.start]
    returning = [tok for tok in in_period if first_seen[tok] < period.start]
    return NewVsReturning(period, total(new), total(returning))


@dataclass(frozen=True, slots=True)
class MonthActivity:
    month_start: date
    complete: bool  # False for a month cut by the window or by as_of: never read as a decline
    active: int
    new: int
    returning: int


def monthly_activity(transactions: Iterable[Transaction], book: CustomerBook) -> list[MonthActivity]:
    txs = list(transactions)
    out = []
    month = book.window.start.replace(day=1)
    while month <= book.as_of:
        nxt = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
        start, end = max(month, book.window.start), min(nxt, book.window.end)
        split = new_vs_returning(txs, DateRange(start, end))
        active = split.new.customers + split.returning.customers
        out.append(MonthActivity(month, start == month and end == nxt, active,
                                 split.new.customers, split.returning.customers))
        month = nxt
    return out
