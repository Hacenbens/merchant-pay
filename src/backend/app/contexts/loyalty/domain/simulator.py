"""Loyalty offer simulator: what a programme could cost, and the sales uplift needed to pay for it.

A SCENARIO, not a forecast: uplift and redemption are the merchant's assumptions, and no causal
uplift is claimed without an experiment. Contribution is only computed with a merchant-entered
gross margin; without it the simulator reports costs and liability only. Nothing here is profit.

Baseline (window of tokenised accepted transactions):
  S   = accepted value of tokenised customers;  P(u) = sum over customers of
        min(cap, floor(uncapped_points_c x (1 + u)))  (uplift spread proportionally over customers)
For a scenario with uplift u and redemption rate r:
  incremental sales        dS = u x S
  points issued            P(u);   reward liability L = P(u) x point_value (face value)
  expected reward cost     R = r x L
  cost on existing sales   R0 = r x P(0) x point_value   (rewards paid on sales you already had)
  total cost               C = R + fixed campaign cost K
  gross contribution       G = m x dS               (only with margin m)
  net scenario contribution N = G - C
Break-even uplift u* = smallest u in [0, 10] with m x u x S >= r x P(u) x point_value + K, found on a
0.1-point grid then refined by bisection (exact with caps and minimum spend); none -> reported.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal

from app.contexts.loyalty.domain.program import ProgramRules, apply_cap
from app.shared.domain.errors import DomainError
from app.shared.domain.money import Money

MAX_UPLIFT = Decimal(10)  # +1000 %
GRID_STEP = Decimal("0.001")


@dataclass(frozen=True, slots=True)
class Scenario:
    name: str  # low | base | high
    uplift: Decimal  # 0.05 = +5 % accepted sales of tokenised customers (assumption)
    redemption_rate: Decimal  # share of issued points redeemed before expiry (assumption)

    def __post_init__(self) -> None:
        if not Decimal(0) <= self.uplift <= MAX_UPLIFT:
            raise DomainError("uplift must be between 0 % and 1000 %")
        if not Decimal(0) <= self.redemption_rate <= Decimal(1):
            raise DomainError("redemption_rate must be between 0 % and 100 %")


@dataclass(frozen=True, slots=True)
class Baseline:
    tokenised_sales: Money
    tokenised_transactions: int
    customers: int
    points_uncapped: dict[str, int]

    @property
    def average_ticket(self) -> Money | None:
        return self.tokenised_sales.average_over(self.tokenised_transactions)


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    scenario: Scenario
    incremental_sales: Money
    points_issued: int
    reward_liability: Money
    reward_cost: Money
    reward_cost_on_existing_sales: Money
    campaign_cost: Money
    total_cost: Money
    gross_contribution: Money | None
    net_contribution: Money | None
    budget_exceeded_by: Money | None  # None when no budget is set or it is respected


@dataclass(frozen=True, slots=True)
class BreakEven:
    scenario: str
    uplift: Decimal | None  # None: not reachable within +1000 %, or no margin given
    incremental_sales: Money | None
    incremental_transactions: int | None  # at the baseline average ticket, rounded up
    reason: str | None  # "margin_required" | "not_reachable"


@dataclass(frozen=True, slots=True)
class SimulationResult:
    baseline: Baseline
    rules: ProgramRules
    margin: Decimal | None
    campaign_cost: Money
    results: list[ScenarioResult]
    break_even: list[BreakEven]


def points_at(rules: ProgramRules, baseline: Baseline, uplift: Decimal) -> int:
    factor = 1 + uplift
    return sum(apply_cap(rules, int((Decimal(p) * factor).to_integral_value(ROUND_FLOOR)))
               for p in baseline.points_uncapped.values())


def _cost_at(rules: ProgramRules, b: Baseline, u: Decimal, r: Decimal, k: Money) -> Money:
    return rules.point_value.scale(Decimal(points_at(rules, b, u)) * r) + k


def run_scenario(rules: ProgramRules, b: Baseline, s: Scenario, margin: Decimal | None,
                 campaign_cost: Money) -> ScenarioResult:
    d_sales = b.tokenised_sales.scale(s.uplift)
    points = points_at(rules, b, s.uplift)
    liability = rules.point_value.scale(Decimal(points))
    cost = liability.scale(s.redemption_rate)
    cost_existing = rules.point_value.scale(Decimal(points_at(rules, b, Decimal(0)))).scale(s.redemption_rate)
    total = cost + campaign_cost
    gross = d_sales.scale(margin) if margin is not None else None
    over = None
    if rules.campaign_budget is not None and total.centimes > rules.campaign_budget.centimes:
        over = total - rules.campaign_budget
    return ScenarioResult(s, d_sales, points, liability, cost, cost_existing, campaign_cost, total,
                          gross, (gross - total) if gross is not None else None, over)


def break_even(rules: ProgramRules, b: Baseline, s: Scenario, margin: Decimal | None,
               campaign_cost: Money) -> BreakEven:
    if margin is None:
        return BreakEven(s.name, None, None, None, "margin_required")

    def gap(u: Decimal) -> int:  # >= 0 means the margin on extra sales covers the costs
        return b.tokenised_sales.scale(margin * u).centimes - _cost_at(rules, b, u, s.redemption_rate,
                                                                      campaign_cost).centimes
    if gap(Decimal(0)) >= 0:
        return _be(s.name, Decimal(0), b)
    lo, u = Decimal(0), Decimal("0.1")
    while u <= MAX_UPLIFT and gap(u) < 0:
        lo, u = u, u + Decimal("0.1")
    if u > MAX_UPLIFT:
        return BreakEven(s.name, None, None, None, "not_reachable")
    hi = u
    while hi - lo > GRID_STEP:
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if gap(mid) >= 0 else (mid, hi)
    return _be(s.name, hi.quantize(GRID_STEP), b)


def _be(name: str, u: Decimal, b: Baseline) -> BreakEven:
    sales = b.tokenised_sales.scale(u)
    ticket = b.average_ticket
    txs = (-(-sales.centimes // ticket.centimes) if ticket and ticket.centimes else None)
    return BreakEven(name, u, sales, txs, None)


def simulate(rules: ProgramRules, b: Baseline, scenarios: list[Scenario], margin: Decimal | None,
             campaign_cost: Money) -> SimulationResult:
    if margin is not None and not Decimal(0) < margin < Decimal(1):
        raise DomainError("gross margin must be between 0 % and 100 % (exclusive)")
    if campaign_cost.centimes < 0:
        raise DomainError("campaign cost cannot be negative")
    if not scenarios:
        raise DomainError("at least one scenario is required")
    return SimulationResult(
        b, rules, margin, campaign_cost,
        [run_scenario(rules, b, s, margin, campaign_cost) for s in scenarios],
        [break_even(rules, b, s, margin, campaign_cost) for s in scenarios],
    )
