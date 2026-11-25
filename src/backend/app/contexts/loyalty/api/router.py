"""Loyalty programme, offer simulator and pilot points ledger. Merchant-scoped; nothing is issued
to real customers and nothing is sent."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from app.container import (
    get_accrue_pilot_uc,
    get_ledger_uc,
    get_list_loyalty_simulations_uc,
    get_loyalty_program_uc,
    get_run_loyalty_simulation_uc,
    get_save_loyalty_program_uc,
    get_scope,
    get_today,
)
from app.contexts.customers.domain.profiles import mask
from app.contexts.loyalty.application.use_cases import (
    AccruePilot,
    GetLedger,
    GetProgram,
    ListSimulations,
    RunLoyaltySimulation,
    SaveProgram,
)
from app.contexts.loyalty.domain.ledger import EntryKind
from app.contexts.loyalty.domain.program import ProgramRules, ProgramVersion
from app.contexts.loyalty.domain.simulator import Scenario
from app.shared.api.schemas import MoneyOut, PeriodOut
from app.shared.domain.merchant_scope import MerchantScope
from app.shared.domain.money import Money

router = APIRouter(prefix="/loyalty", tags=["loyalty"])

Fraction = Annotated[Decimal, Field(ge=0, le=1, max_digits=6, decimal_places=4)]


class LoyaltyRulesIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    points_per_100_dzd: int = Field(ge=1, le=100)
    point_value_centimes: int = Field(gt=0, le=100_000)
    min_eligible_spend_centimes: int = Field(default=0, ge=0, le=10**12)
    cap_points_per_customer: int | None = Field(default=None, ge=1, le=10**9)
    expiry_days: int | None = Field(default=None, ge=7, le=1095)
    campaign_budget_centimes: int | None = Field(default=None, gt=0, le=10**14)

    def to_domain(self) -> ProgramRules:
        b = self.campaign_budget_centimes
        return ProgramRules(
            self.points_per_100_dzd,
            Money(self.point_value_centimes),
            Money(self.min_eligible_spend_centimes),
            self.cap_points_per_customer,
            self.expiry_days,
            Money(b) if b is not None else None,
        )


class LoyaltyRulesOut(BaseModel):
    points_per_100_dzd: int
    point_value: MoneyOut
    min_eligible_spend: MoneyOut
    cap_points_per_customer: int | None
    expiry_days: int | None
    campaign_budget: MoneyOut | None
    reward_rate: float  # face value returned per DZD of eligible spend

    @classmethod
    def of(cls, r: ProgramRules) -> "LoyaltyRulesOut":
        return cls(
            points_per_100_dzd=r.points_per_100_dzd,
            point_value=MoneyOut.of(r.point_value),
            min_eligible_spend=MoneyOut.of(r.min_eligible_spend),
            cap_points_per_customer=r.cap_points_per_customer,
            expiry_days=r.expiry_days,
            campaign_budget=MoneyOut.of(r.campaign_budget) if r.campaign_budget else None,
            reward_rate=float(r.reward_rate),
        )


class LoyaltyProgramOut(BaseModel):
    version: int
    effective_from: date
    created_at: datetime | None
    rules: LoyaltyRulesOut

    @classmethod
    def of(cls, p: ProgramVersion) -> "LoyaltyProgramOut":
        return cls(
            version=p.version,
            effective_from=p.effective_from,
            created_at=p.created_at,
            rules=LoyaltyRulesOut.of(p.rules),
        )


class LoyaltyProgramStateOut(BaseModel):
    program: LoyaltyProgramOut | None  # null: no programme configured yet (all of this is hypothetical)


@router.get("/program", response_model=LoyaltyProgramStateOut)
def get_program(
    scope: MerchantScope = Depends(get_scope), uc: GetProgram = Depends(get_loyalty_program_uc)
) -> LoyaltyProgramStateOut:
    p = uc.execute(scope)
    return LoyaltyProgramStateOut(program=LoyaltyProgramOut.of(p) if p else None)


class LoyaltyProgramIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rules: LoyaltyRulesIn
    effective_from: date


@router.put("/program", response_model=LoyaltyProgramOut)
def save_program(
    body: LoyaltyProgramIn,
    scope: MerchantScope = Depends(get_scope),
    today: date = Depends(get_today),
    uc: SaveProgram = Depends(get_save_loyalty_program_uc),
) -> LoyaltyProgramOut:
    return LoyaltyProgramOut.of(uc.execute(scope, body.rules.to_domain(), body.effective_from, today))


# ---- simulator -----------------------------------------------------------------------------
class LoyaltyScenarioIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=r"^(low|base|high)$")
    uplift: Annotated[Decimal, Field(ge=0, le=10, max_digits=7, decimal_places=4)]
    redemption_rate: Fraction


class LoyaltySimulationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rules: LoyaltyRulesIn
    scenarios: list[LoyaltyScenarioIn] = Field(min_length=1, max_length=3)
    gross_margin: Annotated[Decimal, Field(gt=0, lt=1, max_digits=6, decimal_places=4)] | None = None
    campaign_cost_centimes: int = Field(default=0, ge=0, le=10**14)
    window_days: int = Field(default=90, ge=30, le=365)


class LoyaltyBaselineOut(BaseModel):
    window: PeriodOut
    tokenised_sales: MoneyOut
    tokenised_transactions: int
    customers: int
    average_ticket: MoneyOut | None


class LoyaltyScenarioResultOut(BaseModel):
    name: str
    uplift: float
    redemption_rate: float
    incremental_sales: MoneyOut  # assumption-driven, not a forecast
    points_issued: int
    reward_liability: MoneyOut
    reward_cost: MoneyOut
    reward_cost_on_existing_sales: MoneyOut
    campaign_cost: MoneyOut
    total_cost: MoneyOut
    gross_contribution: MoneyOut | None  # null without a margin assumption
    net_contribution: MoneyOut | None
    budget_exceeded_by: MoneyOut | None


class LoyaltyBreakEvenOut(BaseModel):
    name: str
    uplift: float | None
    incremental_sales: MoneyOut | None
    incremental_transactions: int | None
    reason: str | None


class LoyaltySimulationOut(BaseModel):
    run_id: int
    baseline: LoyaltyBaselineOut
    rules: LoyaltyRulesOut
    gross_margin: float | None
    results: list[LoyaltyScenarioResultOut]
    break_even: list[LoyaltyBreakEvenOut]


def _m(m: Money | None) -> MoneyOut | None:
    return MoneyOut.of(m) if m is not None else None


@router.post("/simulations", response_model=LoyaltySimulationOut, status_code=201)
def run_simulation(
    body: LoyaltySimulationIn,
    scope: MerchantScope = Depends(get_scope),
    today: date = Depends(get_today),
    uc: RunLoyaltySimulation = Depends(get_run_loyalty_simulation_uc),
) -> LoyaltySimulationOut:
    o = uc.execute(
        scope,
        today,
        body.window_days,
        body.rules.to_domain(),
        [Scenario(s.name, s.uplift, s.redemption_rate) for s in body.scenarios],
        body.gross_margin,
        Money(body.campaign_cost_centimes),
    )
    r, b = o.result, o.result.baseline
    return LoyaltySimulationOut(
        run_id=o.run_id,
        baseline=LoyaltyBaselineOut(
            window=PeriodOut.of(o.window),
            tokenised_sales=MoneyOut.of(b.tokenised_sales),
            tokenised_transactions=b.tokenised_transactions,
            customers=b.customers,
            average_ticket=_m(b.average_ticket),
        ),
        rules=LoyaltyRulesOut.of(r.rules),
        gross_margin=float(r.margin) if r.margin is not None else None,
        results=[
            LoyaltyScenarioResultOut(
                name=x.scenario.name,
                uplift=float(x.scenario.uplift),
                redemption_rate=float(x.scenario.redemption_rate),
                incremental_sales=MoneyOut.of(x.incremental_sales),
                points_issued=x.points_issued,
                reward_liability=MoneyOut.of(x.reward_liability),
                reward_cost=MoneyOut.of(x.reward_cost),
                reward_cost_on_existing_sales=MoneyOut.of(x.reward_cost_on_existing_sales),
                campaign_cost=MoneyOut.of(x.campaign_cost),
                total_cost=MoneyOut.of(x.total_cost),
                gross_contribution=_m(x.gross_contribution),
                net_contribution=_m(x.net_contribution),
                budget_exceeded_by=_m(x.budget_exceeded_by),
            )
            for x in r.results
        ],
        break_even=[
            LoyaltyBreakEvenOut(
                name=e.scenario,
                uplift=float(e.uplift) if e.uplift is not None else None,
                incremental_sales=_m(e.incremental_sales),
                incremental_transactions=e.incremental_transactions,
                reason=e.reason,
            )
            for e in r.break_even
        ],
    )


class LoyaltySimulationRunOut(BaseModel):
    id: int
    created_at: datetime
    inputs: dict
    results: dict


@router.get("/simulations", response_model=list[LoyaltySimulationRunOut])
def list_simulations(
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    scope: MerchantScope = Depends(get_scope),
    uc: ListSimulations = Depends(get_list_loyalty_simulations_uc),
) -> list[LoyaltySimulationRunOut]:
    return [
        LoyaltySimulationRunOut(id=r.id, created_at=r.created_at, inputs=r.inputs, results=r.results)
        for r in uc.execute(scope, limit)
    ]


# ---- pilot ledger --------------------------------------------------------------------------
class LoyaltyAccrualOut(BaseModel):
    program_version: int
    created_earn: int
    created_expire: int
    already_recorded: int


@router.post("/ledger/accrue", response_model=LoyaltyAccrualOut)
def accrue(
    scope: MerchantScope = Depends(get_scope),
    today: date = Depends(get_today),
    uc: AccruePilot = Depends(get_accrue_pilot_uc),
) -> LoyaltyAccrualOut:
    r = uc.execute(scope, today)
    return LoyaltyAccrualOut(
        program_version=r.program_version,
        created_earn=r.created_earn,
        created_expire=r.created_expire,
        already_recorded=r.already_recorded,
    )


class LoyaltyEntryOut(BaseModel):
    customer: str  # masked alias, never the raw token
    kind: EntryKind
    points: int
    occurred_on: date
    source_transaction_id: str | None


class LoyaltyLedgerSummaryOut(BaseModel):
    earned: int
    expired: int
    outstanding: int
    customers_with_balance: int
    liability: MoneyOut  # outstanding points x point value (face value)
    budget: MoneyOut | None
    liability_over_budget: MoneyOut | None


class LoyaltyLedgerOut(BaseModel):
    program: LoyaltyProgramOut | None
    summary: LoyaltyLedgerSummaryOut | None
    entries: list[LoyaltyEntryOut]
    total: int
    page: int
    size: int


@router.get("/ledger", response_model=LoyaltyLedgerOut)
def ledger(
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 25,
    scope: MerchantScope = Depends(get_scope),
    uc: GetLedger = Depends(get_ledger_uc),
) -> LoyaltyLedgerOut:
    v = uc.execute(scope, page, size)
    if v is None:
        return LoyaltyLedgerOut(program=None, summary=None, entries=[], total=0, page=page, size=size)
    s = v.summary
    return LoyaltyLedgerOut(
        program=LoyaltyProgramOut.of(v.program),
        total=v.total,
        page=page,
        size=size,
        summary=LoyaltyLedgerSummaryOut(
            earned=s.earned,
            expired=s.expired,
            outstanding=s.outstanding,
            customers_with_balance=s.customers_with_balance,
            liability=MoneyOut.of(s.liability),
            budget=_m(s.budget),
            liability_over_budget=_m(s.liability_over_budget),
        ),
        entries=[
            LoyaltyEntryOut(
                customer=mask(e.customer_token),
                kind=e.kind,
                points=e.points,
                occurred_on=e.occurred_on,
                source_transaction_id=e.source_transaction_id,
            )
            for e in v.entries
        ],
    )
