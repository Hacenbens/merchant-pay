"""Loyalty programme rules (hypothetical, merchant-configured) and the points they would earn.

Earning rule: an ACCEPTED transaction of a tokenised customer with amount >= min_eligible_spend
earns floor(amount / 100 DZD) x points_per_100_dzd points. Integer arithmetic on centimes only.
A per-customer cap limits the points one customer can earn under one programme version.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.contexts.ledger.domain.transaction import Transaction
from app.shared.domain.enums import TransactionStatus
from app.shared.domain.errors import DomainError
from app.shared.domain.money import Money

CENTIMES_PER_100_DZD = 10_000


@dataclass(frozen=True, slots=True)
class ProgramRules:
    points_per_100_dzd: int
    point_value: Money  # face value of one point when redeemed
    min_eligible_spend: Money = Money(0)
    cap_points_per_customer: int | None = None
    expiry_days: int | None = None
    campaign_budget: Money | None = None  # ceiling for reward cost; exceeding it is flagged

    def __post_init__(self) -> None:
        if not 1 <= self.points_per_100_dzd <= 100:
            raise DomainError("points_per_100_dzd must be between 1 and 100")
        if not 0 < self.point_value.centimes <= 100_000:
            raise DomainError("point_value must be between 0.01 and 1,000 DZD")
        if self.min_eligible_spend.centimes < 0:
            raise DomainError("min_eligible_spend cannot be negative")
        if self.cap_points_per_customer is not None and self.cap_points_per_customer < 1:
            raise DomainError("cap_points_per_customer must be at least 1")
        if self.expiry_days is not None and not 7 <= self.expiry_days <= 1095:
            raise DomainError("expiry_days must be between 7 and 1095")
        if self.campaign_budget is not None and self.campaign_budget.centimes <= 0:
            raise DomainError("campaign_budget must be positive")

    @property
    def reward_rate(self) -> Decimal:
        """Face value given back per DZD of eligible spend (e.g. 0.01 = 1 %)."""
        return Decimal(self.points_per_100_dzd * self.point_value.centimes) / CENTIMES_PER_100_DZD

    def points_for(self, amount: Money) -> int:
        if amount.centimes < self.min_eligible_spend.centimes:
            return 0
        return (amount.centimes // CENTIMES_PER_100_DZD) * self.points_per_100_dzd


@dataclass(frozen=True, slots=True)
class ProgramVersion:
    version: int
    rules: ProgramRules
    effective_from: date
    created_at: object = None  # datetime, set by the repository
    created_by: int | None = None


def eligible(transactions: Iterable[Transaction]) -> list[Transaction]:
    """Accepted, tokenised transactions: the only ones a programme can reward."""
    return [t for t in transactions if t.status is TransactionStatus.ACCEPTED and t.customer_token]


def uncapped_points_by_customer(rules: ProgramRules, txs: Iterable[Transaction]) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for t in eligible(txs):
        out[t.customer_token] += rules.points_for(t.amount)
    return dict(out)


def apply_cap(rules: ProgramRules, points: int) -> int:
    return points if rules.cap_points_per_customer is None else min(points, rules.cap_points_per_customer)
