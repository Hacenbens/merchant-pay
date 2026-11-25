"""Run the growth simulator on an observed baseline period and persist the scenario."""

from dataclasses import dataclass
from typing import Protocol

from app.contexts.analytics.domain.kpis import KpiSnapshot, compute_kpis
from app.contexts.identity.domain.model import Merchant
from app.contexts.ledger.domain.transaction import Transaction
from app.contexts.simulation.domain.growth import Assumptions, Baseline, Projection, simulate
from app.contexts.simulation.domain.scenario_lab import (
    LabAssumptions,
    LabBaseline,
    LabProjection,
    goal_for_period,
    lab_baseline,
    project,
)
from app.contexts.simulation.domain.scenario_run import ScenarioRun
from app.shared.domain.date_range import DateRange
from app.shared.domain.merchant_scope import MerchantScope
from app.shared.domain.money import Money


class TransactionReader(Protocol):
    """Port. Implemented by ledger's SqlTransactionRepository (structural typing)."""

    def list_in_period(self, scope: MerchantScope, period: DateRange) -> list[Transaction]: ...


class ScenarioRunRepository(Protocol):
    def save(self, run: ScenarioRun) -> None: ...

    def save_lab(self, merchant_id: str, created_by: int, period: DateRange, name: str,
                 assumptions: LabAssumptions, projection: LabProjection) -> None: ...


class MerchantProfileReader(Protocol):
    """Port for the monthly goal. Implemented by identity's SqlMerchantRepository."""

    def get(self, merchant_id: str) -> Merchant | None: ...


@dataclass(frozen=True, slots=True)
class SimulationResult:
    baseline_period: DateRange
    baseline: Baseline
    baseline_kpis: KpiSnapshot
    assumptions: Assumptions
    projection: Projection
    monthly_goal: Money | None

    @property
    def goal_gap(self) -> Money | None:
        """Projected collection minus the monthly goal: positive means the goal is covered."""
        if self.monthly_goal is None:
            return None
        return self.projection.projected_collection - self.monthly_goal


class RunGrowthSimulation:
    def __init__(self, reader: TransactionReader, scenarios: ScenarioRunRepository,
                 merchants: MerchantProfileReader) -> None:
        self._reader = reader
        self._scenarios = scenarios
        self._merchants = merchants

    def execute(self, scope: MerchantScope, baseline_period: DateRange,
                assumptions: Assumptions) -> SimulationResult:
        kpis = compute_kpis(self._reader.list_in_period(scope, baseline_period))
        # Raises DomainError (-> 422) when the period has no accepted activity: no fake baseline.
        baseline = Baseline.from_kpis(kpis)
        projection = simulate(baseline, assumptions)
        merchant = self._merchants.get(scope.merchant_id)
        result = SimulationResult(baseline_period, baseline, kpis, assumptions, projection,
                                  merchant.monthly_goal if merchant else None)
        self._scenarios.save(ScenarioRun(scope.merchant_id, scope.user_id, baseline_period,
                                         assumptions, projection))
        return result


# ---- Scenario Lab: named, channel-aware scenarios with an exact bridge -------------------------
@dataclass(frozen=True, slots=True)
class LabResult:
    baseline: LabBaseline
    monthly_goal: Money | None
    goal_for_period: Money | None
    scenarios: list[tuple[str, LabProjection]]


class RunScenarioLab:
    def __init__(self, reader: TransactionReader, scenarios: ScenarioRunRepository,
                 merchants: MerchantProfileReader) -> None:
        self._reader, self._scenarios, self._merchants = reader, scenarios, merchants

    def execute(self, scope: MerchantScope, period: DateRange,
                named: list[tuple[str, LabAssumptions]]) -> LabResult:
        baseline = lab_baseline(self._reader.list_in_period(scope, period), period)
        merchant = self._merchants.get(scope.merchant_id)
        goal = merchant.monthly_goal if merchant else None
        goal_p = goal_for_period(goal, period)
        results = [(name, project(baseline, a, goal_p)) for name, a in named]
        for name, p in results:
            self._scenarios.save_lab(scope.merchant_id, scope.user_id, period, name, p.assumptions, p)
        return LabResult(baseline, goal, goal_p, results)
