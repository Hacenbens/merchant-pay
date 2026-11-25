"""Loyalty use cases: programme versions (owner-only, audited), simulations, pilot points ledger."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Protocol

from app.contexts.ledger.domain.transaction import Transaction
from app.contexts.loyalty.domain.ledger import LedgerEntry, LedgerSummary, plan_accrual, summarise
from app.contexts.loyalty.domain.program import (
    ProgramRules,
    ProgramVersion,
    eligible,
    uncapped_points_by_customer,
)
from app.contexts.loyalty.domain.simulator import Baseline, Scenario, SimulationResult, simulate
from app.shared.domain.date_range import DateRange
from app.shared.domain.errors import DomainError, Forbidden, NotFound
from app.shared.domain.merchant_scope import MerchantScope
from app.shared.domain.money import Money

HISTORY_START = date(2000, 1, 1)


class TransactionReader(Protocol):
    def list_in_period(self, scope: MerchantScope, period: DateRange) -> list[Transaction]: ...


class ProgramRepository(Protocol):
    def current(self, scope: MerchantScope) -> ProgramVersion | None: ...

    def add(self, scope: MerchantScope, rules: ProgramRules, effective_from: date) -> ProgramVersion: ...


class LedgerRepository(Protocol):
    def entries(self, scope: MerchantScope, version: int) -> list[LedgerEntry]: ...

    def add_all(self, scope: MerchantScope, entries: list[LedgerEntry]) -> None:
        """Insert; the (merchant, idempotency_key) unique constraint rejects any replay."""
        ...


@dataclass(frozen=True, slots=True)
class SimulationRun:
    id: int
    created_at: datetime
    inputs: dict
    results: dict


class SimulationRunRepository(Protocol):
    def add(self, scope: MerchantScope, inputs: dict, results: dict) -> SimulationRun: ...

    def recent(self, scope: MerchantScope, limit: int) -> list[SimulationRun]: ...


class AuditLog(Protocol):
    def record(self, actor_id: int, action: str, entity_ref: str) -> None: ...


def _require_owner(scope: MerchantScope) -> None:
    if scope.role != "owner":
        raise Forbidden("Only the merchant owner can change the loyalty programme")


def rules_to_dict(r: ProgramRules) -> dict:
    return {"points_per_100_dzd": r.points_per_100_dzd, "point_value_centimes": r.point_value.centimes,
            "min_eligible_spend_centimes": r.min_eligible_spend.centimes,
            "cap_points_per_customer": r.cap_points_per_customer, "expiry_days": r.expiry_days,
            "campaign_budget_centimes": r.campaign_budget.centimes if r.campaign_budget else None}


def rules_from_dict(d: dict) -> ProgramRules:
    budget = d.get("campaign_budget_centimes")
    return ProgramRules(d["points_per_100_dzd"], Money(d["point_value_centimes"]),
                        Money(d.get("min_eligible_spend_centimes", 0)), d.get("cap_points_per_customer"),
                        d.get("expiry_days"), Money(budget) if budget is not None else None)


# ---- programme -----------------------------------------------------------------------------
class GetProgram:
    def __init__(self, programs: ProgramRepository) -> None:
        self._programs = programs

    def execute(self, scope: MerchantScope) -> ProgramVersion | None:
        return self._programs.current(scope)


class SaveProgram:
    def __init__(self, programs: ProgramRepository, audit: AuditLog) -> None:
        self._programs, self._audit = programs, audit

    def execute(self, scope: MerchantScope, rules: ProgramRules, effective_from: date,
                today: date) -> ProgramVersion:
        _require_owner(scope)
        if not today - timedelta(days=365) <= effective_from <= today + timedelta(days=365):
            raise DomainError("effective_from must be within one year of today")
        saved = self._programs.add(scope, rules, effective_from)
        self._audit.record(scope.user_id, "loyalty.program_saved",
                           f"merchant:{scope.merchant_id} version:{saved.version}")
        return saved


# ---- simulation ----------------------------------------------------------------------------
def build_baseline(rules: ProgramRules, txs: list[Transaction]) -> Baseline:
    el = eligible(txs)
    return Baseline(Money.total(t.amount for t in el), len(el), len({t.customer_token for t in el}),
                    uncapped_points_by_customer(rules, el))


@dataclass(frozen=True, slots=True)
class SimulationOutcome:
    run_id: int
    window: DateRange
    result: SimulationResult


class RunLoyaltySimulation:
    def __init__(self, reader: TransactionReader, runs: SimulationRunRepository) -> None:
        self._reader, self._runs = reader, runs

    def execute(self, scope: MerchantScope, today: date, window_days: int, rules: ProgramRules,
                scenarios: list[Scenario], margin: Decimal | None, campaign_cost: Money) -> SimulationOutcome:
        if not 30 <= window_days <= 365:
            raise DomainError("window_days must be between 30 and 365")
        window = DateRange.last_n_days(today, window_days)
        baseline = build_baseline(rules, self._reader.list_in_period(scope, window))
        result = simulate(rules, baseline, scenarios, margin, campaign_cost)
        inputs = {"window": [window.start.isoformat(), window.last_day.isoformat()],
                  "rules": rules_to_dict(rules), "margin": str(margin) if margin is not None else None,
                  "campaign_cost_centimes": campaign_cost.centimes,
                  "scenarios": [{"name": s.name, "uplift": str(s.uplift),
                                 "redemption_rate": str(s.redemption_rate)} for s in scenarios]}
        summary = {"baseline_sales_centimes": baseline.tokenised_sales.centimes,
                   "customers": baseline.customers,
                   "scenarios": [{"name": r.scenario.name, "total_cost_centimes": r.total_cost.centimes,
                                  "net_contribution_centimes": r.net_contribution.centimes
                                  if r.net_contribution else None} for r in result.results],
                   "break_even": [{"name": b.scenario, "uplift": str(b.uplift) if b.uplift is not None
                                   else None, "reason": b.reason} for b in result.break_even]}
        run = self._runs.add(scope, inputs, summary)
        return SimulationOutcome(run.id, window, result)


class ListSimulations:
    def __init__(self, runs: SimulationRunRepository) -> None:
        self._runs = runs

    def execute(self, scope: MerchantScope, limit: int = 10) -> list[SimulationRun]:
        return self._runs.recent(scope, limit)


# ---- pilot ledger --------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class AccrualReport:
    program_version: int
    created_earn: int
    created_expire: int
    already_recorded: int


class AccruePilot:
    def __init__(self, programs: ProgramRepository, ledger: LedgerRepository,
                 reader: TransactionReader, audit: AuditLog) -> None:
        self._programs, self._ledger, self._reader, self._audit = programs, ledger, reader, audit

    def execute(self, scope: MerchantScope, today: date) -> AccrualReport:
        _require_owner(scope)
        program = self._programs.current(scope)
        if program is None:
            raise NotFound("No loyalty programme configured")
        existing = self._ledger.entries(scope, program.version)
        txs = self._reader.list_in_period(scope, DateRange(HISTORY_START, today + timedelta(days=1)))
        new = plan_accrual(program, txs, existing, today)
        self._ledger.add_all(scope, new)
        report = AccrualReport(program.version, sum(1 for e in new if e.kind.value == "earn"),
                               sum(1 for e in new if e.kind.value == "expire"), len(existing))
        self._audit.record(scope.user_id, "loyalty.pilot_accrued",
                           f"merchant:{scope.merchant_id} version:{program.version} "
                           f"earn:{report.created_earn} expire:{report.created_expire}")
        return report


@dataclass(frozen=True, slots=True)
class LedgerView:
    program: ProgramVersion
    summary: LedgerSummary
    entries: list[LedgerEntry]  # newest first, paginated
    total: int


class GetLedger:
    def __init__(self, programs: ProgramRepository, ledger: LedgerRepository) -> None:
        self._programs, self._ledger = programs, ledger

    def execute(self, scope: MerchantScope, page: int = 1, size: int = 25) -> LedgerView | None:
        program = self._programs.current(scope)
        if program is None:
            return None
        entries = self._ledger.entries(scope, program.version)
        ordered = sorted(entries, key=lambda e: (e.occurred_on, e.idempotency_key), reverse=True)
        start = (page - 1) * size
        return LedgerView(program, summarise(program, entries), ordered[start:start + size], len(entries))
