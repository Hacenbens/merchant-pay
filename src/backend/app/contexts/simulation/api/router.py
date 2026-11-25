from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.container import get_run_growth_simulation, get_run_scenario_lab, get_scope, get_today
from app.contexts.simulation.application.run_simulation import RunGrowthSimulation, RunScenarioLab
from app.contexts.simulation.domain.growth import Assumptions
from app.contexts.simulation.domain.scenario_lab import BridgeStep, ChannelShift, LabAssumptions
from app.shared.api.schemas import MoneyOut, PeriodOut, period_from_query
from app.shared.domain.enums import Channel
from app.shared.domain.merchant_scope import MerchantScope

router = APIRouter(prefix="/simulations", tags=["simulation"])


class SimulationIn(BaseModel):
    baseline_from: date | None = None
    baseline_to: date | None = None
    volume_growth: float = Field(default=0.15, ge=-1, le=10)
    acceptance_change: float = Field(default=0.0, ge=-1, le=1)  # absolute points
    ticket_change: float = Field(default=0.0, gt=-1, le=10)  # relative


class BaselineOut(BaseModel):
    period: PeriodOut
    total_count: int
    accepted_count: int
    acceptance_share: float  # accepted / all initiated: makes count x share x ticket reconcile
    average_ticket: MoneyOut
    gross_collection: MoneyOut


class AssumptionsOut(BaseModel):
    volume_growth: float
    acceptance_change: float
    ticket_change: float


class ProjectionOut(BaseModel):
    projected_count: int
    projected_accepted_count: float
    projected_acceptance_share: float
    projected_average_ticket: MoneyOut
    projected_collection: MoneyOut
    delta_collection: MoneyOut
    delta_pct: float | None


class SimulationOut(BaseModel):
    baseline: BaselineOut
    assumptions: AssumptionsOut
    projection: ProjectionOut
    monthly_goal: MoneyOut | None
    goal_gap: MoneyOut | None  # projection - goal; positive means the goal is covered


@router.post("/growth", response_model=SimulationOut)
def growth(
    body: SimulationIn,
    scope: MerchantScope = Depends(get_scope),
    today: date = Depends(get_today),
    uc: RunGrowthSimulation = Depends(get_run_growth_simulation),
) -> SimulationOut:
    assumptions = Assumptions(
        volume_growth=Decimal(str(body.volume_growth)),
        acceptance_change=Decimal(str(body.acceptance_change)),
        ticket_change=Decimal(str(body.ticket_change)),
    )
    r = uc.execute(scope, period_from_query(body.baseline_from, body.baseline_to, today), assumptions)
    k, p = r.baseline_kpis, r.projection
    return SimulationOut(
        baseline=BaselineOut(
            period=PeriodOut.of(r.baseline_period),
            total_count=k.total_count,
            accepted_count=k.accepted_count,
            acceptance_share=float(r.baseline.acceptance_share),
            average_ticket=MoneyOut.of(r.baseline.average_ticket),
            gross_collection=MoneyOut.of(k.gross_collected),
        ),
        assumptions=AssumptionsOut(
            volume_growth=float(r.assumptions.volume_growth),
            acceptance_change=float(r.assumptions.acceptance_change),
            ticket_change=float(r.assumptions.ticket_change),
        ),
        projection=ProjectionOut(
            projected_count=p.projected_count,
            projected_accepted_count=float(p.projected_accepted_count),
            projected_acceptance_share=float(p.projected_acceptance_share),
            projected_average_ticket=MoneyOut.of(p.projected_average_ticket),
            projected_collection=MoneyOut.of(p.projected_collection),
            delta_collection=MoneyOut.of(p.delta_collection),
            delta_pct=float(p.delta_pct) if p.delta_pct is not None else None,
        ),
        monthly_goal=MoneyOut.of(r.monthly_goal) if r.monthly_goal else None,
        goal_gap=MoneyOut.of(r.goal_gap) if r.goal_gap is not None else None,
    )


# ---- Scenario Lab ------------------------------------------------------------------------------
Rate = Annotated[Decimal, Field(max_digits=7, decimal_places=4)]


class LabShiftIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_channel: Channel
    to_channel: Channel
    share: Annotated[Decimal, Field(gt=0, le=1, max_digits=5, decimal_places=4)]


class LabScenarioIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=r"^(conservative|base|ambitious)$")
    volume_growth: Rate = Decimal(0)
    acceptance_change: Rate = Decimal(0)  # absolute points: 0.02 = +2 points
    ticket_change: Rate = Decimal(0)  # relative
    shifts: list[LabShiftIn] = Field(default_factory=list, max_length=4)


class LabIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    baseline_from: date | None = None
    baseline_to: date | None = None
    scenarios: list[LabScenarioIn] = Field(min_length=1, max_length=3)


class LabChannelBaselineOut(BaseModel):
    channel: Channel
    initiated: int
    accepted: int
    declined: int
    acceptance_share: float  # accepted / initiated
    decline_share: float  # declined / initiated
    average_ticket: MoneyOut | None
    accepted_amount: MoneyOut
    declined_amount: MoneyOut


class LabBaselineOut(BaseModel):
    period: PeriodOut
    initiated: int
    collection: MoneyOut  # = gross accepted collection of the period
    declined_amount: MoneyOut
    channels: list[LabChannelBaselineOut]


class LabBridgeStepOut(BaseModel):
    step: BridgeStep
    amount: MoneyOut


class LabChannelProjectionOut(BaseModel):
    channel: Channel
    volume: float
    acceptance_share: float
    average_ticket: MoneyOut
    collection: MoneyOut
    declined_value: MoneyOut


class LabScenarioOut(BaseModel):
    name: str
    volume_growth: float
    acceptance_change: float
    ticket_change: float
    shifts: list[LabShiftIn]
    transactions: int
    collection: MoneyOut
    delta: MoneyOut
    delta_pct: float | None
    declined_value: MoneyOut  # estimate: acceptance gains assumed to come from fewer declines
    bridge: list[LabBridgeStepOut]  # steps add up exactly to delta
    channels: list[LabChannelProjectionOut]
    acceptance_capped: list[Channel]
    required_volume_growth: float | None  # to reach the pro-rated monthly goal


class LabOut(BaseModel):
    baseline: LabBaselineOut
    monthly_goal: MoneyOut | None
    goal_for_period: MoneyOut | None  # monthly goal x baseline days / 30
    scenarios: list[LabScenarioOut]


@router.post("/lab", response_model=LabOut)
def scenario_lab(
    body: LabIn,
    scope: MerchantScope = Depends(get_scope),
    today: date = Depends(get_today),
    uc: RunScenarioLab = Depends(get_run_scenario_lab),
) -> LabOut:
    named = [
        (
            s.name,
            LabAssumptions(
                s.volume_growth,
                s.acceptance_change,
                s.ticket_change,
                tuple(ChannelShift(x.from_channel, x.to_channel, x.share) for x in s.shifts),
            ),
        )
        for s in body.scenarios
    ]
    r = uc.execute(scope, period_from_query(body.baseline_from, body.baseline_to, today), named)
    b = r.baseline
    m = lambda x: MoneyOut.of(x) if x is not None else None  # noqa: E731
    return LabOut(
        baseline=LabBaselineOut(
            period=PeriodOut.of(b.period),
            initiated=b.initiated,
            collection=MoneyOut.of(b.collection),
            declined_amount=MoneyOut.of(b.declined_amount),
            channels=[
                LabChannelBaselineOut(
                    channel=c.channel,
                    initiated=c.initiated,
                    accepted=c.accepted,
                    declined=c.declined,
                    acceptance_share=float(c.acceptance),
                    decline_share=float(c.decline),
                    average_ticket=MoneyOut.of(c.accepted_amount.average_over(c.accepted))
                    if c.accepted
                    else None,
                    accepted_amount=MoneyOut.of(c.accepted_amount),
                    declined_amount=MoneyOut.of(c.declined_amount),
                )
                for c in b.channels
            ],
        ),
        monthly_goal=m(r.monthly_goal),
        goal_for_period=m(r.goal_for_period),
        scenarios=[
            LabScenarioOut(
                name=name,
                volume_growth=float(p.assumptions.volume_growth),
                acceptance_change=float(p.assumptions.acceptance_change),
                ticket_change=float(p.assumptions.ticket_change),
                shifts=[
                    LabShiftIn(from_channel=x.from_channel, to_channel=x.to_channel, share=x.share)
                    for x in p.assumptions.shifts
                ],
                transactions=p.transactions,
                collection=MoneyOut.of(p.collection),
                delta=MoneyOut.of(p.delta),
                delta_pct=float(p.delta_pct) if p.delta_pct is not None else None,
                declined_value=MoneyOut.of(p.declined_value),
                bridge=[LabBridgeStepOut(step=st, amount=MoneyOut.of(v)) for st, v in p.bridge],
                channels=[
                    LabChannelProjectionOut(
                        channel=c.channel,
                        volume=float(c.volume),
                        acceptance_share=float(c.acceptance),
                        average_ticket=MoneyOut.of(c.ticket),
                        collection=MoneyOut.of(c.collection),
                        declined_value=MoneyOut.of(c.declined_value),
                    )
                    for c in p.channels
                ],
                acceptance_capped=p.acceptance_capped,
                required_volume_growth=float(p.required_volume_growth)
                if p.required_volume_growth is not None
                else None,
            )
            for name, p in r.scenarios
        ],
    )
